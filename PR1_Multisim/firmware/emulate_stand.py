"""
Проверка прошивки стенда без железа: ядро Cortex-M3 эмулируется Unicorn,
RCC/GPIOA/ADC1/TIM1 — упрощённые модели регистров.

Запуск:  uv run --with unicorn --with pyelftools python emulate_stand.py
"""
import sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_SP, UC_CPU_ARM_CORTEX_M3

FLASH, RAM = 0x08000000, 0x20000000
RCC, GPIOA, ADC1, TIM1 = 0x40021000, 0x40010800, 0x40012400, 0x40012C00


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
        self.pins_in = 0

    def read(self, uc, off, size, _):
        return self.pins_in if off == 0x08 else self.r.get(off, 0)

    def write(self, uc, off, size, value, _):
        if off == 0x10:  # BSRR
            self.r[0x0C] = (self.r[0x0C] | (value & 0xFFFF)) & ~(value >> 16) & 0xFFFF
        else:
            self.r[off] = value


class Adc(Regs):
    """SR=0x00, CR2=0x08, DR=0x4C. Калибровка завершается сразу, EOC готов всегда."""
    def __init__(self):
        super().__init__()
        self.value = 0

    def read(self, uc, off, size, _):
        if off == 0x00:
            return 0x2  # EOC
        if off == 0x4C:
            return self.value
        return self.r.get(off, 0)

    def write(self, uc, off, size, value, _):
        if off == 0x08:
            value &= ~((1 << 2) | (1 << 3))  # CAL, RSTCAL сбрасываются аппаратно
        self.r[off] = value


def load(path):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M3)
    uc.mem_map(FLASH, 64 * 1024)
    uc.mem_map(RAM, 20 * 1024)
    with open(path, "rb") as f:
        for seg in ELFFile(f).iter_segments():
            if seg["p_type"] == "PT_LOAD" and seg["p_filesz"]:
                uc.mem_write(seg["p_paddr"], seg.data())
    periph = {"rcc": Regs(), "gpio": Gpio(), "adc": Adc(), "tim": Regs()}
    for base, dev in ((RCC, "rcc"), (GPIOA, "gpio"), (ADC1, "adc"), (TIM1, "tim")):
        d = periph[dev]
        uc.mmio_map(base, 0x400, d.read, None, d.write, None)
    sp, reset = (int.from_bytes(uc.mem_read(FLASH + i, 4), "little") for i in (0, 4))
    uc.reg_write(UC_ARM_REG_SP, sp)
    uc.reg_write(UC_ARM_REG_PC, reset)
    return uc, periph


def run(uc, steps=20000):
    uc.emu_start(uc.reg_read(UC_ARM_REG_PC) | 1, 0xFFFFFFFF, count=steps)


ok = True


def expect(name, cond):
    global ok
    print(f"  [{'OK' if cond else 'FAIL'}] {name}")
    ok &= bool(cond)


def suite(title, cfgr, psc):
    uc, p = load("build/stand_stm32.elf")
    gpio, adc, tim, rcc = p["gpio"], p["adc"], p["tim"], p["rcc"]
    rcc.r[0x04] = cfgr
    print(f"=== {title} ===")

    def state():
        odr, ccer = gpio.r[0x0C], tim.r.get(0x20, 0)
        return (odr >> 1) & 1, (odr >> 2) & 1, ccer & 1, tim.r.get(0x2C), tim.r.get(0x34)

    gpio.pins_in = 0x0001          # кнопка отпущена: PA0 = 1 через R3
    adc.value = 1000
    run(uc)
    apb2 = rcc.r.get(0x18, 0)
    print("Инициализация:")
    expect("RCC_APB2ENR: IOPAEN, ADC1EN, TIM1EN", apb2 & 0x4 and apb2 & 0x200 and apb2 & 0x800)
    expect("RCC_CFGR.ADCPRE = /6", (rcc.r[0x04] >> 14) & 3 == 2)
    crl, crh = gpio.r[0x00], gpio.r[0x04]
    expect(f"GPIOA_CRL = 0x{crl:08X}: PA0 вход, PA1/PA2 выход, PA4 аналог",
           crl & 0xF == 0x4 and (crl >> 4) & 0xF == 0x2 and (crl >> 8) & 0xF == 0x2 and (crl >> 16) & 0xF == 0x0)
    expect(f"GPIOA_CRH = 0x{crh:08X}: PA8 AF push-pull 2 МГц", crh & 0xF == 0xA)
    expect("ADC1_SQR3 = 4 (канал PA4)", adc.r.get(0x34) == 4)
    expect(f"TIM1: PSC = {tim.r.get(0x28)} (ожидается {psc}), CCMR1 = PWM1, BDTR.MOE = 1, CR1.CEN = 1",
           tim.r.get(0x28) == psc and (tim.r.get(0x18, 0) >> 4) & 7 == 6
           and tim.r.get(0x44, 0) & 0x8000 and tim.r.get(0x00, 0) & 1)

    print("Работа:")
    for btn, pot, want in [(1, 1000, (0, 0, 0)), (0, 1000, (1, 0, 1)), (0, 3500, (1, 1, 1)),
                           (1, 3500, (0, 1, 0)), (0, 0, (1, 0, 1)), (0, 4095, (1, 1, 1))]:
        gpio.pins_in, adc.value = btn, pot
        run(uc)
        hl1, hl2, buz, arr, ccr = state()
        tone = f", тон {1_000_000 // (arr + 1)} Гц, CCR1/ARR = {ccr}/{arr}" if buz else ""
        expect(f"кнопка {'отпущена' if btn else 'нажата  '}, АЦП {pot:4}: HL1={hl1} HL2={hl2} зуммер={buz}{tone}",
               (hl1, hl2, buz) == want)
        if buz:
            expect("  скважность 50 %", ccr == (arr + 1) // 2)
    expect("при АЦП=4095 тон 4000 Гц (ARR = 249)", state()[3] == 249)


suite("HSI 8 МГц (system_stm32f1xx.c от ST)", 0x00000000, 7)
# SWS = PLL, PLLSRC = HSE, PLLMUL = x9 — как после SetSysClockTo72() в CooCox
suite("HSE + PLL = 72 МГц (CooCox, SYSCLK_FREQ_72MHz)", (0b10 << 2) | (1 << 16) | (7 << 18), 71)

sys.exit(0 if ok else 1)
