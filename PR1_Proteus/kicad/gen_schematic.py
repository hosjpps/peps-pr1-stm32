"""Схема ПР1 (Proteus): STM32F103C8, SA1 (SW-SPDT) -> PA0, PA1 -> R1 -> HL1 -> GND.

Запуск из этой папки:  python3 gen_schematic.py
Результат: pr1_gpio_io.kicad_sch/.pdf/.png, отчёт ERC и проверка нетлиста.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../tools"))
import kicad_gen as k  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
G = k.GREEN

LAYOUT = "gost_portrait.kicad_wks"
s = k.Sheet("pr1_gpio_io", "Устройство ввода-вывода\\nСхема электрическая\\nпринципиальная",
            paper="A4", portrait=True, date="2026-09-30", rev="1", company="РТУ МИРЭА",
            comments=["ПР1.ПЭПС.001 Э3", "Васин С.А.", ""], sheet_layout=LAYOUT)

MCU = s.place("DD1", "MCU_ST_STM32F1", "STM32F103C_8-B_Tx", 88.9, 101.6, value="STM32F103C8T6",
              ref_at=(73.66, 58.42), val_at=(73.66, 144.78))

# --- питание МК: VBAT, VDD x3, VDDA -> +3V3; VSS x3, VSSA -> GND ---
top = [s.pin(MCU, n) for n in ("1", "24", "36", "48", "9")]
rail_y = top[0][1] - 5.08
for p in top:
    s.wire(p, (p[0], rail_y), color=G)
s.wire(*[(p[0], rail_y) for p in top])
for p in top[1:-1]:
    s.junction((p[0], rail_y))
cx = top[2][0]
s.place("#PWR01", "power", "+3V3", cx, rail_y - 2.54, hide_ref=True, val_at=(cx - 1.27, rail_y - 6.35))
s.wire((cx, rail_y), (cx, rail_y - 2.54))
s.junction((cx, rail_y))
s.place("#FLG01", "power", "PWR_FLAG", top[0][0] - 10.16, rail_y, hide_ref=True, hide_val=True)
s.wire((top[0][0] - 10.16, rail_y), (top[0][0], rail_y))

vss, vssa = s.pin(MCU, "23"), s.pin(MCU, "8")
gy = vss[1] + 5.08
s.wire(vss, (vss[0], gy), color=G)
s.wire(vssa, (vssa[0], gy), color=G)
s.wire((vss[0], gy), (vssa[0], gy))
s.place("#PWR02", "power", "GND", vss[0], gy + 2.54, hide_ref=True, val_at=(vss[0] - 1.27, gy + 7.62))
s.wire((vss[0], gy), (vss[0], gy + 2.54))
s.junction((vss[0], gy))
s.place("#FLG02", "power", "PWR_FLAG", vssa[0] + 5.08, gy, hide_ref=True, hide_val=True)
s.wire((vssa[0], gy), (vssa[0] + 5.08, gy))

# --- NRST -> +3V3, BOOT0 -> GND (как в базовой схеме преподавателя) ---
nrst, boot0 = s.pin(MCU, "7"), s.pin(MCU, "44")
s.wire(nrst, (nrst[0] - 7.62, nrst[1]), color=G)
s.place("#PWR03", "power", "+3V3", nrst[0] - 7.62, nrst[1], hide_ref=True,
        val_at=(nrst[0] - 11.43, nrst[1] - 3.81))
s.wire(boot0, (boot0[0] - 7.62, boot0[1]), (boot0[0] - 7.62, boot0[1] + 5.08), color=G)
s.place("#PWR04", "power", "GND", boot0[0] - 7.62, boot0[1] + 5.08, hide_ref=True,
        val_at=(boot0[0] - 8.89, boot0[1] + 10.16))

# --- вход: SA1 SW-SPDT, общий контакт -> PA0, A -> +3V3, C -> GND ---
pa0 = s.pin(MCU, "10")
s.place("SA1", "Switch", "SW_SPDT", pa0[0] + 20.32, pa0[1], value="SW-SPDT",
        ref_at=(pa0[0] + 17.78, pa0[1] - 5.08), val_at=(pa0[0] + 17.78, pa0[1] + 6.35))
s.wire(pa0, s.pin("SA1", "2"), color=G)
a, c = s.pin("SA1", "1"), s.pin("SA1", "3")
s.wire(a, (a[0] + 5.08, a[1]), (a[0] + 5.08, a[1] - 5.08))
s.place("#PWR05", "power", "+3V3", a[0] + 5.08, a[1] - 5.08, hide_ref=True,
        val_at=(a[0] + 3.81, a[1] - 8.89))
s.wire(c, (c[0] + 10.16, c[1]), (c[0] + 10.16, c[1] + 5.08))
s.place("#PWR06", "power", "GND", c[0] + 10.16, c[1] + 5.08, hide_ref=True,
        val_at=(c[0] + 8.89, c[1] + 10.16))

# --- выход: PA1 -> R1 220 -> HL1 (анод) -> катод -> GND ---
pa1 = s.pin(MCU, "11")
ly = pa1[1] + 17.78
s.place("R1", "Device", "R", pa1[0] + 15.24, ly, rot=90, value="220",
        ref_at=(pa1[0] + 13.97, ly - 3.81), val_at=(pa1[0] + 13.97, ly + 4.45))
s.wire(pa1, (pa1[0] + 5.08, pa1[1]), (pa1[0] + 5.08, ly), s.pin("R1", "2"), color=G)
s.place("HL1", "Device", "LED", pa1[0] + 30.48, ly, rot=180, value="LED-GREEN",
        ref_at=(pa1[0] + 27.94, ly - 3.81), val_at=(pa1[0] + 27.94, ly + 5.08))
s.wire(s.pin("R1", "1"), s.pin("HL1", "2"))
kpin = s.pin("HL1", "1")
s.wire(kpin, (kpin[0] + 5.08, kpin[1]), (kpin[0] + 5.08, kpin[1] + 5.08))
s.place("#PWR07", "power", "GND", kpin[0] + 5.08, kpin[1] + 5.08, hide_ref=True,
        val_at=(kpin[0] + 3.81, kpin[1] + 10.16))

# --- неиспользуемые выводы ---
used = {"1", "24", "36", "48", "9", "23", "35", "47", "8", "7", "44", "10", "11"}
for num in s.parts[MCU]["pins"]:
    if num not in used:
        s.no_connect(s.pin(MCU, num))

path = s.save(HERE)

print("Нетлист:")
ok, nets = k.check_nets(path, [
    {"DD1/10", "SA1/2"},
    {"DD1/11", "R1/2"},
    {"R1/1", "HL1/2"},
    {"DD1/1", "DD1/24", "DD1/36", "DD1/48", "DD1/9", "DD1/7", "SA1/1", "#PWR01/1", "#PWR03/1",
     "#PWR05/1", "#FLG01/1"},
    {"DD1/23", "DD1/35", "DD1/47", "DD1/8", "DD1/44", "SA1/3", "HL1/1", "#PWR02/1", "#PWR04/1",
     "#PWR06/1", "#PWR07/1", "#FLG02/1"},
])
rpt, counts = k.erc(path)
print("ERC (сообщений, ошибок, предупреждений):", counts)
k.export_png(path, f"{HERE}/pr1_gpio_io.png", sheet_layout=LAYOUT)
k.export_crop(f"{HERE}/pr1_gpio_io.pdf", f"{HERE}/pr1_gpio_io_crop.png")
sys.exit(0 if ok and counts and counts[1] == "0" else 1)
