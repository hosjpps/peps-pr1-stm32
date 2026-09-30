"""
Проверка прошивки без Proteus: ядро Cortex-M3 эмулируется Unicorn,
регистры RCC и GPIOA — простой моделью. Прошивка стартует с вектора сброса
(startup -> SystemInit -> main), затем на PA0 подаются 1 и 0 и проверяется PA1.

Запуск:  uv run --with unicorn --with pyelftools python emulate_gpio.py
"""
import sys
from elftools.elf.elffile import ELFFile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_THUMB, UC_MODE_MCLASS
from unicorn.arm_const import UC_ARM_REG_PC, UC_ARM_REG_SP, UC_CPU_ARM_CORTEX_M3

FLASH, RAM = 0x08000000, 0x20000000
RCC, GPIOA = 0x40021000, 0x40010800
CRL, IDR, ODR, BSRR, BRR = 0x00, 0x08, 0x0C, 0x10, 0x14


class Gpio:
    def __init__(self):
        self.regs = {CRL: 0x44444444, 0x04: 0x44444444, ODR: 0}
        self.pins_in = 0  # уровни, подаваемые снаружи на входы

    def read(self, uc, off, size, _):
        if off == IDR:
            return self.pins_in & 0xFFFF
        return self.regs.get(off, 0)

    def write(self, uc, off, size, value, _):
        if off == BSRR:
            odr = self.regs[ODR]
            odr |= value & 0xFFFF
            odr &= ~(value >> 16) & 0xFFFF
            self.regs[ODR] = odr
        elif off == BRR:
            self.regs[ODR] &= ~value & 0xFFFF
        else:
            self.regs[off] = value


def load(path):
    uc = Uc(UC_ARCH_ARM, UC_MODE_THUMB | UC_MODE_MCLASS)
    uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_M3)
    uc.mem_map(FLASH, 64 * 1024)
    uc.mem_map(RAM, 20 * 1024)
    with open(path, "rb") as f:
        for seg in ELFFile(f).iter_segments():
            if seg["p_type"] == "PT_LOAD" and seg["p_filesz"]:
                uc.mem_write(seg["p_paddr"], seg.data())

    rcc = {}
    uc.mmio_map(RCC, 0x400,
                lambda u, off, sz, d: rcc.get(off, 0), None,
                lambda u, off, sz, v, d: rcc.__setitem__(off, v), None)
    gpio = Gpio()
    uc.mmio_map(GPIOA, 0x400, gpio.read, None, gpio.write, None)

    sp, reset = (int.from_bytes(uc.mem_read(FLASH + i, 4), "little") for i in (0, 4))
    uc.reg_write(UC_ARM_REG_SP, sp)
    uc.reg_write(UC_ARM_REG_PC, reset)
    return uc, rcc, gpio


def run(uc, steps=5000):
    uc.emu_start(uc.reg_read(UC_ARM_REG_PC) | 1, 0xFFFFFFFF, count=steps)


def check(path, expected_crl_low, pa0_to_pa1, extra=None):
    uc, rcc, gpio = load(path)
    run(uc)
    ok = True

    def expect(name, cond):
        nonlocal ok
        print(f"  [{'OK' if cond else 'FAIL'}] {name}")
        ok &= cond

    expect("RCC_APB2ENR.IOPAEN = 1", rcc.get(0x18, 0) & 0x4 != 0)
    crl = gpio.regs[CRL]
    expect(f"GPIOA_CRL = 0x{crl:08X} (младший байт 0x{expected_crl_low:02X})",
           crl & 0xFF == expected_crl_low and crl >> 8 == 0x444444)
    if extra:
        extra(gpio, expect)
    for pa0, pa1 in pa0_to_pa1:
        gpio.pins_in = (gpio.pins_in & ~1) | pa0
        run(uc)
        got = (gpio.regs[ODR] >> 1) & 1
        led = "горит" if got else "погашен"
        expect(f"PA0 = {pa0} -> PA1 = {got} (светодиод {led})", got == pa1)
    return ok


print("PR1_STM32_GPIO_IO.elf — плавающий вход, SW-SPDT:")
ok1 = check("build/PR1_STM32_GPIO_IO.elf", 0x24, [(1, 1), (0, 0), (1, 1), (0, 0)])

print("PR1_STM32_GPIO_IO_PULLUP.elf — вход с подтяжкой, кнопка на GND:")
ok2 = check("build/PR1_STM32_GPIO_IO_PULLUP.elf", 0x28, [(1, 0), (0, 1), (1, 0)],
            extra=lambda g, e: e("GPIOA_ODR.ODR0 = 1 (подтяжка к VDD)", g.regs[ODR] & 1 == 1))

sys.exit(0 if ok1 and ok2 else 1)
