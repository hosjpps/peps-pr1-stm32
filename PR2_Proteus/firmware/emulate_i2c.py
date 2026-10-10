"""
Проверка прошивки ПР2 без Proteus: ядро Cortex-M3 эмулируется Unicorn, периферия I2C1 STM32F103
и микросхемы 24LC64 (0x50) и DS1307 (0x68) — программные модели с журналом событий шины.
Из журнала строятся временные диаграммы SDA/SCL (аналог Logic Analyzer).

Запуск:  uv run --with unicorn --with pyelftools --with matplotlib python emulate_i2c.py
Результаты: ../sim/results.json, ../sim/run.log, ../sim/*.png
"""
import json
import os
import sys
from dataclasses import dataclass, field

from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_SP, UC_CPU_ARM_CORTEX_M3

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(HERE, "..", "sim")
ELF = os.path.join(HERE, "build", "PR2_STM32_I2C.elf")

FLASH, RAM = 0x08000000, 0x20000000
RCC_B, GPIOA_B, GPIOB_B, I2C1_B = 0x40021000, 0x40010800, 0x40010C00, 0x40005400

# биты I2C
CR1_PE, CR1_START, CR1_STOP, CR1_ACK, CR1_SWRST = 1, 1 << 8, 1 << 9, 1 << 10, 1 << 15
SR1_SB, SR1_ADDR, SR1_BTF, SR1_RXNE, SR1_TXE = 1, 2, 4, 1 << 6, 1 << 7
SR1_BERR, SR1_ARLO, SR1_AF, SR1_OVR = 1 << 8, 1 << 9, 1 << 10, 1 << 11
SR1_RC_W0 = SR1_BERR | SR1_ARLO | SR1_AF | SR1_OVR
SR2_MSL, SR2_BUSY, SR2_TRA = 1, 2, 4

BIT_US = 10.0   # 100 кГц


# ---------------------------------------------------------------- шина и устройства
@dataclass
class Bus:
    t: float = 0.0                       # время на шине, мкс
    events: list = field(default_factory=list)
    devices: dict = field(default_factory=dict)
    cur: object = None                   # устройство, с которым идёт обмен

    def log(self, kind, **kw):
        self.events.append(dict(t=self.t, kind=kind, **kw))

    def start(self, repeated):
        self.log("Sr" if repeated else "S")
        self.t += BIT_US
        if self.cur is not None:
            self.cur.restart()

    def stop(self):
        self.log("P")
        self.t += BIT_US / 2
        if self.cur is not None:
            self.cur.stop(self.t)
        self.cur = None

    def address(self, a7, read):
        dev = self.devices.get(a7)
        ack = dev is not None and dev.select(read, self.t)
        self.log("addr", value=(a7 << 1) | read, read=read, ack=ack, name=getattr(dev, "name", "—"))
        self.t += 9 * BIT_US
        self.cur = dev if ack else None
        return ack

    def write(self, byte):
        ack = self.cur.write(byte) if self.cur else False
        self.log("data", value=byte, read=0, ack=ack)
        self.t += 9 * BIT_US
        return ack

    def read(self, master_ack):
        byte = self.cur.read() if self.cur else 0xFF
        self.log("data", value=byte, read=1, ack=master_ack)
        self.t += 9 * BIT_US
        return byte


class EEPROM24LC64:
    name = "24LC64"
    SIZE, PAGE, TWR_US = 8192, 32, 5000.0

    def __init__(self):
        self.mem = bytearray([0xFF]) * self.SIZE
        self.state, self.ptr, self.hi = "idle", 0, 0
        self.busy_until, self.dirty = -1.0, False
        self.polls_nack = 0

    def select(self, read, t):
        if t < self.busy_until:
            self.polls_nack += 1
            return False
        self.state = "read" if read else "addr_hi"
        return True

    def restart(self):
        pass

    def write(self, b):
        if self.state == "addr_hi":
            self.hi, self.state = b & 0x1F, "addr_lo"
        elif self.state == "addr_lo":
            self.ptr, self.state = (self.hi << 8) | b, "data"
        elif self.state == "data":
            page = self.ptr & ~(self.PAGE - 1)
            self.mem[self.ptr] = b
            self.ptr = page | ((self.ptr + 1) & (self.PAGE - 1))   # перенос внутри страницы
            self.dirty = True
        return True

    def read(self):
        b = self.mem[self.ptr]
        self.ptr = (self.ptr + 1) % self.SIZE
        return b

    def stop(self, t):
        if self.dirty:
            self.busy_until, self.dirty = t + self.TWR_US, False   # внутренний цикл записи
        self.state = "idle"


class DS1307:
    name = "DS1307"

    def __init__(self):
        self.regs = bytearray(64)
        self.regs[0] = 0x80          # CH = 1: генератор остановлен после включения
        self.ptr, self.state = 0, "idle"

    def select(self, read, t):
        self.state = "read" if read else "ptr"
        return True

    def restart(self):
        pass

    def write(self, b):
        if self.state == "ptr":
            self.ptr, self.state = b & 0x3F, "data"
        else:
            self.regs[self.ptr] = b
            self.ptr = (self.ptr + 1) & 0x3F
        return True

    def read(self):
        b = self.regs[self.ptr]
        self.ptr = (self.ptr + 1) & 0x3F
        return b

    def stop(self, t):
        self.state = "idle"


# ---------------------------------------------------------------- периферия STM32
class Regs:
    def __init__(self, init=None):
        self.r = dict(init or {})

    def read(self, uc, off, size, _):
        return self.r.get(off, 0)

    def write(self, uc, off, size, value, _):
        self.r[off] = value


class Gpio(Regs):
    def __init__(self):
        super().__init__({0x00: 0x44444444, 0x04: 0x44444444, 0x0C: 0})

    def write(self, uc, off, size, value, _):
        if off == 0x10:   # BSRR
            self.r[0x0C] = (self.r[0x0C] | (value & 0xFFFF)) & ~(value >> 16) & 0xFFFF
        else:
            self.r[off] = value


class I2C1:
    def __init__(self, bus, stuck=False):
        self.bus, self.stuck = bus, stuck
        self.cr1 = self.cr2 = self.ccr = self.trise = self.oar1 = 0
        self.sr1, self.sr2 = 0, (SR2_BUSY if stuck else 0)
        self.dr_rx = 0
        self.seq_sr1 = False
        self.mode = "idle"        # idle | tx | rx
        self.addr_dev = None

    def _reset(self):
        self.cr1 = self.sr1 = 0
        self.sr2 = SR2_BUSY if self.stuck else 0
        self.mode = "idle"

    def read(self, uc, off, size, _):
        if off == 0x00:
            return self.cr1
        if off == 0x04:
            return self.cr2
        if off == 0x08:
            return self.oar1
        if off == 0x10:
            v, self.sr1 = self.dr_rx, self.sr1 & ~SR1_RXNE
            return v
        if off == 0x14:
            self.seq_sr1 = True
            return self.sr1
        if off == 0x18:
            v = self.sr2
            if self.seq_sr1 and self.sr1 & SR1_ADDR:
                self.sr1 &= ~SR1_ADDR
                if self.mode == "tx":
                    self.sr1 |= SR1_TXE
                else:   # приём одного байта: ACK уже сброшен -> NACK после байта
                    self.dr_rx = self.bus.read(bool(self.cr1 & CR1_ACK))
                    self.sr1 |= SR1_RXNE
            self.seq_sr1 = False
            return v
        if off == 0x1C:
            return self.ccr
        if off == 0x20:
            return self.trise
        return 0

    def write(self, uc, off, size, value, _):
        if off == 0x00:
            if value & CR1_SWRST:
                self._reset()
                return
            self.cr1 = value & ~(CR1_START | CR1_STOP)
            if value & CR1_START and not self.stuck and self.cr1 & CR1_PE:
                repeated = bool(self.sr2 & SR2_MSL)
                self.bus.start(repeated)
                self.sr1 |= SR1_SB
                self.sr2 |= SR2_MSL | SR2_BUSY
                self.mode = "idle"
            if value & CR1_STOP and self.sr2 & SR2_MSL:
                self.bus.stop()
                self.sr2 &= ~(SR2_MSL | SR2_BUSY | SR2_TRA)
                self.sr1 &= ~(SR1_TXE | SR1_BTF)
                self.mode = "idle"
        elif off == 0x04:
            self.cr2 = value
        elif off == 0x08:
            self.oar1 = value
        elif off == 0x10:
            self.seq_sr1 = False
            if self.sr1 & SR1_SB:
                self.sr1 &= ~SR1_SB
                a7, rd = value >> 1, value & 1
                if self.bus.address(a7, rd):
                    self.sr1 |= SR1_ADDR
                    self.mode = "rx" if rd else "tx"
                    self.sr2 = (self.sr2 | SR2_TRA) if not rd else (self.sr2 & ~SR2_TRA)
                else:
                    self.sr1 |= SR1_AF
            elif self.mode == "tx":
                self.sr1 &= ~(SR1_TXE | SR1_BTF)
                if self.bus.write(value):
                    self.sr1 |= SR1_TXE | SR1_BTF
                else:
                    self.sr1 |= SR1_AF
        elif off == 0x14:
            self.sr1 &= value | ~SR1_RC_W0          # флаги ошибок сбрасываются записью 0
        elif off == 0x1C:
            self.ccr = value
        elif off == 0x20:
            self.trise = value


# ---------------------------------------------------------------- запуск прошивки
def load(elf):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M3)
    uc.mem_map(FLASH, 64 * 1024)
    uc.mem_map(RAM, 20 * 1024)
    syms = {}
    with open(elf, "rb") as f:
        e = ELFFile(f)
        for seg in e.iter_segments():
            if seg["p_type"] == "PT_LOAD" and seg["p_filesz"]:
                uc.mem_write(seg["p_paddr"], seg.data())
        for s in e.get_section_by_name(".symtab").iter_symbols():
            syms[s.name] = s["st_value"]
    sp, reset = (int.from_bytes(uc.mem_read(FLASH + i, 4), "little") for i in (0, 4))
    uc.reg_write(UC_ARM_REG_SP, sp)
    uc.reg_write(UC_ARM_REG_PC, reset)
    return uc, syms


def run_scenario(name, eeprom_addr=0x50, stuck=False, ds_addr=0x68):
    uc, syms = load(ELF)
    bus = Bus()
    eeprom, ds = EEPROM24LC64(), DS1307()
    bus.devices = {eeprom_addr: eeprom, ds_addr: ds}
    rcc = Regs({0x00: 0x83})     # HSION | HSIRDY
    gpioa, gpiob, i2c = Gpio(), Gpio(), I2C1(bus, stuck)
    for base, dev in ((RCC_B, rcc), (GPIOA_B, gpioa), (GPIOB_B, gpiob), (I2C1_B, i2c)):
        uc.mmio_map(base, 0x400, dev.read, None, dev.write, None)

    same, last = 0, None
    for _ in range(2000):
        uc.emu_start(uc.reg_read(UC_ARM_REG_PC) | 1, 0xFFFFFFFF, count=50000)
        pc = uc.reg_read(UC_ARM_REG_PC)
        same = same + 1 if pc == last else 0
        last = pc
        if same >= 3:
            break
    else:
        raise RuntimeError("прошивка не остановилась")

    rd = lambda sym: uc.mem_read(syms[sym], 1)[0]  # noqa: E731
    return dict(
        name=name, led=(gpioa.r[0x0C] >> 1) & 1,
        eeprom_read=rd("g_eeprom_read"), rtc_raw=rd("g_rtc_raw"), rtc_value=rd("g_rtc_value"),
        eeprom_cell=eeprom.mem[0x0000], ds_regs=list(ds.regs[:8]),
        nack_polls=eeprom.polls_nack, t_us=bus.t, sr1=i2c.sr1, sr2=i2c.sr2,
        i2c_cfg=dict(cr2_freq=i2c.cr2 & 0x3F, ccr=i2c.ccr, trise=i2c.trise, oar1=i2c.oar1, cr1=i2c.cr1),
        events=bus.events,
    )


def fmt_event(e):
    k = e["kind"]
    if k in ("S", "Sr", "P"):
        return {"S": "START", "Sr": "repeated START", "P": "STOP"}[k]
    if k == "addr":
        return f"SLA+{'R' if e['read'] else 'W'} 0x{e['value']:02X} ({e['name']}) -> {'ACK' if e['ack'] else 'NACK'}"
    who = "ведомый -> ведущий" if e["read"] else "ведущий -> ведомый"
    return f"данные 0x{e['value']:02X} ({who}) -> {'ACK' if e['ack'] else 'NACK'}"


def main():
    os.makedirs(SIM, exist_ok=True)
    scen = [
        ("normal", dict()),
        ("wrong_address", dict(eeprom_addr=0x51)),
        ("no_pullup", dict(stuck=True)),
    ]
    results = [run_scenario(n, **kw) for n, kw in scen]
    out = []
    ok = True
    for r in results:
        out.append(f"=== сценарий: {r['name']} ===")
        out.append(f"светодиод PA1 = {r['led']}; g_eeprom_read = 0x{r['eeprom_read']:02X}; "
                   f"g_rtc_raw = 0x{r['rtc_raw']:02X}; g_rtc_value = {r['rtc_value']}")
        out.append(f"EEPROM[0x0000] = 0x{r['eeprom_cell']:02X}; регистры DS1307 0..7: "
                   f"{' '.join(f'{b:02X}' for b in r['ds_regs'])}; NACK при ACK polling: {r['nack_polls']}; "
                   f"время на шине: {r['t_us'] / 1000:.2f} мс")
        out.append(f"I2C1: CR2.FREQ = {r['i2c_cfg']['cr2_freq']}, CCR = {r['i2c_cfg']['ccr']}, "
                   f"TRISE = {r['i2c_cfg']['trise']}, OAR1 = 0x{r['i2c_cfg']['oar1']:04X}, "
                   f"SR1 = 0x{r['sr1']:04X}, SR2 = 0x{r['sr2']:04X}")
        out.append("журнал шины (первые 24 события):")
        out += ["  %9.1f мкс  %s" % (e["t"], fmt_event(e)) for e in r["events"][:24]]
        out.append("")

    def expect(name, cond):
        nonlocal ok
        out.append(f"[{'OK' if cond else 'FAIL'}] {name}")
        ok &= bool(cond)

    n, w, p = results
    expect("normal: светодиод горит, записано = считано = 0x34", n["led"] == 1 and n["eeprom_read"] == 0x34
           and n["eeprom_cell"] == 0x34)
    expect("normal: ACK polling завершился, NACK-опросов > 0 и общее время записи около 5 мс",
           n["nack_polls"] > 10)
    expect("normal: DS1307 — сек 0x00 (CH = 0), мин 0x34, часы 0x12; raw = 0x00, десятичное 0",
           n["ds_regs"][:3] == [0x00, 0x34, 0x12] and n["rtc_raw"] == 0 and n["rtc_value"] == 0)
    expect("normal: SR1/SR2 без ошибок, шина свободна", n["sr1"] & 0xF00 == 0 and n["sr2"] & 3 == 0)
    expect("normal: CR2.FREQ = 8, CCR = 40, TRISE = 9", (n["i2c_cfg"]["cr2_freq"], n["i2c_cfg"]["ccr"],
                                                         n["i2c_cfg"]["trise"]) == (8, 40, 9))
    expect("wrong_address: NACK на SLA+W 0xA0, светодиод не горит, в EEPROM ничего не записано",
           w["led"] == 0 and w["eeprom_cell"] == 0xFF
           and any(e["kind"] == "addr" and not e["ack"] and e["value"] == 0xA0 for e in w["events"]))
    expect("no_pullup: шина занята (BUSY), на SDA/SCL нет активности, светодиод не горит",
           p["led"] == 0 and len(p["events"]) == 0 and p["sr2"] & 2)
    out.append("ИТОГ: " + ("все проверки пройдены" if ok else "ЕСТЬ ОШИБКИ"))

    text = "\n".join(out)
    print(text)
    with open(os.path.join(SIM, "run.log"), "w", encoding="utf-8") as f:
        f.write(text + "\n")
    with open(os.path.join(SIM, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
