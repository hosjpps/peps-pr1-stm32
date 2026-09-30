"""Схема учебного стенда на STM32F103C8 с периферией (ПР1, Multisim/KiCad).

Периферия: SB1 (кнопка, PA0), HL1/HL2 (светодиоды, PA1/PA2),
RP1 (потенциометр, PA4 = ADC1_IN4), HA1 (зуммер через VT1, PA8 = TIM1_CH1).
Запуск из этой папки:  python3 gen_schematic.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../tools"))
import kicad_gen as k  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
G = k.GREEN
LAYOUT = "gost_portrait.kicad_wks"

s = k.Sheet("stand_stm32", "Учебный стенд на STM32F103C8\\\\nСхема электрическая\\\\nпринципиальная",
            paper="A4", portrait=True, date="2026-09-30", rev="1", company="РТУ МИРЭА",
            comments=["ПР1.ПЭПС.002 Э3", "Васин С.А.", ""], sheet_layout=LAYOUT)

pwr_n = [0]


def power(kind, pt, label_dx=-1.27):
    pwr_n[0] += 1
    ref = f"#PWR{pwr_n[0]:02d}"
    dy = -3.81 if kind == "+3V3" else 5.08
    s.place(ref, "power", kind, pt[0], pt[1], hide_ref=True, val_at=(pt[0] + label_dx, pt[1] + dy))


def R(ref, x, y, value, horizontal=False):
    rot = 90 if horizontal else 0
    ra = (x - 2.54, y - 3.81) if horizontal else (x + 2.54, y - 1.27)
    va = (x - 2.54, y + 4.45) if horizontal else (x + 2.54, y + 1.27)
    s.place(ref, "Device", "R", x, y, rot=rot, value=value, ref_at=ra, val_at=va)


def C(ref, x, y, value, horizontal=False):
    rot = 90 if horizontal else 0
    ra = (x - 5.08, y - 4.45) if horizontal else (x + 2.54, y - 1.27)
    va = (x + 0.635, y - 4.45) if horizontal else (x + 2.54, y + 1.27)
    s.place(ref, "Device", "C", x, y, rot=rot, value=value, ref_at=ra, val_at=va)


MX, MY = 88.9, 127.0
MCU = s.place("DD1", "MCU_ST_STM32F1", "STM32F103C_8-B_Tx", MX, MY, value="STM32F103C8T6",
              ref_at=(MX - 15.24, MY - 39.37), val_at=(MX - 15.24, MY + 39.37))
P = lambda n: s.pin(MCU, n)  # noqa: E731

# ---------------- питание ----------------
top = [P(n) for n in ("1", "24", "36", "48", "9")]
ry = top[0][1] - 12.7
for p in top:
    s.wire(p, (p[0], ry), color=G)
flg_x, c4_x, c5_x = top[0][0] - 10.16, top[-1][0] + 7.62, top[-1][0] + 17.78
s.wire((flg_x, ry), *[(p[0], ry) for p in top], (c4_x, ry), (c5_x, ry))
for x in [p[0] for p in top] + [c4_x]:
    s.junction((x, ry))
s.place("#FLG01", "power", "PWR_FLAG", flg_x, ry, hide_ref=True, hide_val=True)
power("+3V3", (MX, ry - 2.54))
s.wire((MX, ry), (MX, ry - 2.54))
C("C4", c4_x, ry + 3.81, "0.1u")
C("C5", c5_x, ry + 3.81, "0.1u")
power("GND", s.pin("C4", "2"))
power("GND", s.pin("C5", "2"))

vss, vssa = P("23"), P("8")
gy = vss[1] + 5.08
s.wire(vss, (vss[0], gy), color=G)
s.wire(vssa, (vssa[0], gy), color=G)
s.wire((vss[0], gy), (vssa[0], gy), (vssa[0] + 5.08, gy))
s.junction((vssa[0], gy))
s.place("#FLG02", "power", "PWR_FLAG", vssa[0] + 5.08, gy, hide_ref=True, hide_val=True)
power("GND", (vss[0], gy + 2.54))
s.wire((vss[0], gy), (vss[0], gy + 2.54))
s.junction((vss[0], gy))

# ---------------- сброс: R1 к +3V3, C3 к GND ----------------
nrst = P("7")
node = (nrst[0] - 10.16, nrst[1] - 15.24)
s.wire(nrst, (node[0], nrst[1]), node, color=G)
s.label("6", (node[0], nrst[1]), 0)
R("R1", node[0], node[1] - 7.62, "10k")
s.wire(s.pin("R1", "2"), node)
power("+3V3", s.pin("R1", "1"))
C("C3", node[0] - 7.62, node[1], "0.1u", horizontal=True)
s.wire(node, s.pin("C3", "2"))
c3 = s.pin("C3", "1")
s.wire(c3, (c3[0] - 5.08, c3[1]), (c3[0] - 5.08, c3[1] + 2.54))
power("GND", (c3[0] - 5.08, c3[1] + 2.54))
s.junction(node)

# ---------------- BOOT0 через R2 к GND ----------------
boot0 = P("44")
R("R2", boot0[0] - 10.16, boot0[1], "10k", horizontal=True)
s.wire(boot0, s.pin("R2", "2"), color=G)
s.label("7", (boot0[0] - 3.81, boot0[1]), 0)
r2 = s.pin("R2", "1")
s.wire(r2, (r2[0] - 7.62, r2[1]), (r2[0] - 7.62, r2[1] + 2.54))
power("GND", (r2[0] - 7.62, r2[1] + 2.54))

# ---------------- кварц 8 МГц: ZQ1, C1, C2 ----------------
pd0, pd1 = P("5"), P("6")
xy = 147.32
s.place("ZQ1", "Device", "Crystal", MX - 33.02, xy, value="8MHz", ref_at=(MX - 35.56, xy - 3.81),
        val_at=(MX - 35.56, xy + 3.81))
z1, z2 = s.pin("ZQ1", "1"), s.pin("ZQ1", "2")
s.wire(pd0, (pd0[0] - 5.08, pd0[1]), (pd0[0] - 5.08, xy), z2, color=G)
s.label("8", (pd0[0] - 5.08, pd0[1]), 0)
low = xy + 17.78
s.wire(pd1, (pd1[0] - 2.54, pd1[1]), (pd1[0] - 2.54, low), (z1[0], low), z1, color=G)
s.label("9", (pd1[0] - 2.54, low), 0)
C("C1", z1[0] - 8.89, xy + 6.35, "22p")
s.wire(z1, (z1[0] - 8.89, xy), s.pin("C1", "1"))
C("C2", z2[0], xy + 6.35, "22p")
s.wire(z2, s.pin("C2", "1"))
power("GND", s.pin("C1", "2"))
power("GND", s.pin("C2", "2"))
s.junction(z1)
s.junction(z2)

# ---------------- справа: периферия ----------------
pa0, pa1, pa2, pa4, pa8 = P("10"), P("11"), P("12"), P("14"), P("29")

# SB1 + R3 (подтяжка) на PA0
n0 = (pa0[0] + 30.48, pa0[1] - 22.86)
s.wire(pa0, (pa0[0] + 17.78, pa0[1]), (pa0[0] + 17.78, n0[1]), n0, color=G)
s.label("1", (pa0[0] + 17.78, n0[1]), 0)
R("R3", n0[0], n0[1] - 7.62, "10k")
s.wire(s.pin("R3", "2"), n0)
power("+3V3", s.pin("R3", "1"))
s.place("SB1", "Switch", "SW_Push", n0[0] + 12.7, n0[1], value="Кнопка",
        ref_at=(n0[0] + 10.16, n0[1] - 5.08), val_at=(n0[0] + 8.89, n0[1] + 3.81))
s.wire(n0, s.pin("SB1", "1"))
sb = s.pin("SB1", "2")
s.wire(sb, (sb[0] + 5.08, sb[1]), (sb[0] + 5.08, sb[1] + 5.08))
power("GND", (sb[0] + 5.08, sb[1] + 5.08))
s.junction(n0)

# HL1 (PA1) и HL2 (PA2) через R4, R5
led_x = pa1[0] + 45.72
R("R4", led_x - 15.24, pa1[1], "330", horizontal=True)
mid1 = (pa1[0] + 15.24, pa1[1])
s.wire(pa1, mid1, s.pin("R4", "1"), color=G)
s.label("2", mid1, 0)
s.place("HL1", "Device", "LED", led_x, pa1[1], rot=180, value="Зелёный",
        ref_at=(led_x - 2.54, pa1[1] - 3.81), val_at=(led_x - 3.81, pa1[1] + 4.45))
s.wire(s.pin("R4", "2"), s.pin("HL1", "2"))
y2 = pa2[1] + 10.16
R("R5", led_x - 15.24, y2, "330", horizontal=True)
s.wire(pa2, (pa2[0] + 7.62, pa2[1]), (pa2[0] + 7.62, y2), s.pin("R5", "1"), color=G)
s.label("3", (pa2[0] + 7.62, y2), 0)
s.place("HL2", "Device", "LED", led_x, y2, rot=180, value="Красный",
        ref_at=(led_x - 2.54, y2 - 3.81), val_at=(led_x - 3.81, y2 + 4.45))
s.wire(s.pin("R5", "2"), s.pin("HL2", "2"))
k1, k2 = s.pin("HL1", "1"), s.pin("HL2", "1")
kx = k1[0] + 6.35
s.wire(k1, (kx, k1[1]), (kx, k2[1]), (kx, k2[1] + 2.54))
s.wire(k2, (kx, k2[1]))
s.junction((kx, k2[1]))
power("GND", (kx, k2[1] + 2.54))

# RP1 на PA4 (ADC1_IN4)
py = pa4[1] + 25.4
s.place("RP1", "Device", "R_Potentiometer", pa4[0] + 30.48, py, mirror="y", value="10k",
        ref_at=(pa4[0] + 36.83, py - 1.27), val_at=(pa4[0] + 36.83, py + 1.27))
s.wire(pa4, (pa4[0] + 5.08, pa4[1]), (pa4[0] + 5.08, py), s.pin("RP1", "2"), color=G)
s.label("4", (pa4[0] + 5.08, py), 0)
power("+3V3", s.pin("RP1", "1"))
power("GND", s.pin("RP1", "3"))

# HA1 через ключ VT1 на PA8 (TIM1_CH1), VD1 — защитный диод
by = pa8[1] + 38.1
vx = pa8[0] + 50.8
s.place("VT1", "Transistor_BJT", "Q_NPN_CBE", vx, by, value="BC547",
        ref_at=(vx + 5.08, by - 1.27), val_at=(vx + 5.08, by + 1.27))
R("R6", vx - 15.24, by, "1k", horizontal=True)
s.wire(pa8, (pa8[0] + 2.54, pa8[1]), (pa8[0] + 2.54, by), s.pin("R6", "1"), color=G)
s.label("5", (pa8[0] + 2.54, by), 0)
s.wire(s.pin("R6", "2"), s.pin("VT1", "2"))
e = s.pin("VT1", "3")
power("GND", e)
c = s.pin("VT1", "1")
hx, hy = c[0] + 2.54, c[1] - 7.62
s.place("HA1", "Device", "Buzzer", hx, hy, value="Зуммер", ref_at=(hx - 15.24, hy - 1.27),
        val_at=(hx - 15.24, hy + 1.27))
hp, hm = s.pin("HA1", "1"), s.pin("HA1", "2")
s.place("VD1", "Device", "D", hp[0] + 7.62, hy, rot=270, value="1N4148",
        ref_at=(hp[0] + 10.16, hy - 1.27), val_at=(hp[0] + 10.16, hy + 1.27))
kd, ad = s.pin("VD1", "1"), s.pin("VD1", "2")
tp = (hp[0], kd[1] - 1.27)
bm = (hm[0], ad[1] + 1.27)
s.wire(hp, tp, (hp[0], tp[1] - 2.54))
power("+3V3", (hp[0], tp[1] - 2.54))
s.wire(kd, (kd[0], tp[1]), tp)
s.wire(hm, bm, c)
s.wire(ad, (ad[0], bm[1]), bm)
s.junction(tp)
s.junction(bm)

# ---------------- неиспользуемые выводы ----------------
used = {"1", "24", "36", "48", "9", "23", "35", "47", "8", "7", "44", "5", "6",
        "10", "11", "12", "14", "29"}
for num in s.parts[MCU]["pins"]:
    if num not in used:
        s.no_connect(P(num))

path = s.save(HERE)

print("Нетлист:")
V33 = {"DD1/1", "DD1/24", "DD1/36", "DD1/48", "DD1/9", "C4/1", "C5/1", "R1/1", "R3/1", "RP1/1",
       "HA1/1", "VD1/1"}
GNDN = {"DD1/23", "DD1/35", "DD1/47", "DD1/8", "C4/2", "C5/2", "C3/1", "R2/1", "C1/2", "C2/2",
        "SB1/2", "HL1/1", "HL2/1", "RP1/3", "VT1/3"}
ok, nets = k.check_nets(path, [
    {"DD1/10", "R3/2", "SB1/1"},          # 1 PA0 кнопка
    {"DD1/11", "R4/1"},                   # 2 PA1
    {"DD1/12", "R5/1"},                   # 3 PA2
    {"DD1/14", "RP1/2"},                  # 4 PA4 АЦП
    {"DD1/29", "R6/1"},                   # 5 PA8 ШИМ
    {"DD1/7", "R1/2", "C3/2"},            # 6 NRST
    {"DD1/44", "R2/2"},                   # 7 BOOT0
    {"DD1/5", "ZQ1/2", "C2/1"},           # 8 OSC_IN
    {"DD1/6", "ZQ1/1", "C1/1"},           # 9 OSC_OUT
    {"R4/2", "HL1/2"}, {"R5/2", "HL2/2"}, {"R6/2", "VT1/2"},
    {"HA1/2", "VD1/2", "VT1/1"},
    V33, GNDN,
])
rpt, counts = k.erc(path)
print("ERC (сообщений, ошибок, предупреждений):", counts)
if counts and counts[0] != "0":
    print(rpt)
k.export_png(path, f"{HERE}/stand_stm32.png", sheet_layout=LAYOUT)
k.export_crop(f"{HERE}/stand_stm32.pdf", f"{HERE}/stand_stm32_crop.png")
sys.exit(0 if ok and counts and counts[1] == "0" else 1)
