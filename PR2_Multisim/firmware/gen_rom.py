"""Образ внешнего ПЗУ для задания 2 и контрольная сумма (сумма байт по модулю 256).

Параметры совпадают с константами в src/rom_test.c: ZZZ = 0x0800, K = 100 байт.
Выход: rom_image.bin (K байт, первый байт = адрес ZZZ), rom_image.hex (Intel HEX, с адреса ZZZ),
src/rom_checksum.h (константа для резидентной памяти программ МК).
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ZZZ, K = 0x0800, 100

image = bytes((i * 7 + 3) & 0xFF for i in range(K))   # детерминированное содержимое
checksum = sum(image) & 0xFF


def ihex_record(addr, rtype, data=b""):
    body = bytes([len(data), addr >> 8, addr & 0xFF, rtype]) + data
    return ":" + (body + bytes([(-sum(body)) & 0xFF])).hex().upper()


def main():
    with open(os.path.join(HERE, "rom_image.bin"), "wb") as f:
        f.write(image)
    lines = [ihex_record(ZZZ + off, 0, image[off:off + 16]) for off in range(0, K, 16)]
    lines.append(ihex_record(0, 1))
    with open(os.path.join(HERE, "rom_image.hex"), "w") as f:
        f.write("\n".join(lines) + "\n")
    with open(os.path.join(HERE, "src", "rom_checksum.h"), "w", encoding="utf-8") as f:
        f.write("/* Сформировано gen_rom.py: сумма K байт образа ПЗУ по модулю 256 */\n"
                f"#define ROM_CHECKSUM 0x{checksum:02X}\n")
    print(f"ZZZ=0x{ZZZ:04X} K={K} контрольная сумма=0x{checksum:02X} ({checksum})")


if __name__ == "__main__":
    main()
