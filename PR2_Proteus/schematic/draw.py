"""Схема общей шины I2C: STM32F103C8 + 24LC64 + DS1307 (рис. 9.22 методички).
Запуск:  python3 draw.py  ->  pr2_i2c.png / pr2_i2c.pdf, проверка списка цепей."""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "../../tools"))
import schem  # noqa: E402

s = schem.Sheet(160, 175, title="Подключение EEPROM 24LC64 и часов DS1307 к STM32F103C8 по шине I2C\nСхема электрическая принципиальная",
                code="ПР2.ПЭПС.002 Э3", author="Васин С.А.", group="ЭФБО-17-24")
ax = s.ax
G = schem.GREEN

# ---- DD1: STM32F103C8T6 (показаны используемые выводы) ----
s.ic("DD1", "STM32F103C8T6 (LQFP48)", 24, 42, 30,
     left=[(7, "NRST", "+3V3"), (44, "BOOT0", "GND")],
     right=[(42, "PB6/SCL", "~SCL"), (43, "PB7/SDA", "~SDA"), (11, "PA1", "LED")],
     top=[(1, "VBAT", "~+3V3"), (9, "VDDA", "~+3V3"), (24, "VDD", "+3V3"), (36, "VDD", "~+3V3"),
          (48, "VDD", "~+3V3")],
     bottom=[(23, "VSS", "~GND"), (35, "VSS", "GND"), (47, "VSS", "~GND"), (8, "VSSA", "~GND")])
s.text(24, 76, "Показаны используемые выводы DD1", size=5, style="italic")

# ---- DD2: 24LC64, DD3: DS1307 ----
s.ic("DD2", "24LC64", 100, 30, 26,
     left=[(6, "SCL", "~SCL"), (5, "SDA", "~SDA")],
     right=[(1, "A0", "GND"), (2, "A1", "GND"), (3, "A2", "GND"), (7, "WP", "GND")],
     top=[(8, "VCC", "+3V3")], bottom=[(4, "VSS", "GND")])
s.ic("DD3", "DS1307", 100, 84, 26,
     left=[(6, "SCL", "~SCL"), (5, "SDA", "~SDA"), (1, "X1", "XTAL1"), (2, "X2", "XTAL2")],
     right=[(7, "SQW/OUT", "NC"), (3, "VBAT", "GND")],
     top=[(8, "VCC", "+5V")], bottom=[(4, "GND", "GND")])
s.text(100, 24, "адрес 0x50", size=5, style="italic")
s.text(100, 78, "адрес 0x68", size=5, style="italic")

# ---- линии шины I2C ----
def wire(*pts):
    ax.plot([p[0] for p in pts], [p[1] for p in pts], color=G, lw=0.6)


def dot(x, y):
    ax.plot([x], [y], "o", color=G, ms=2.2)


pin_y = lambda top, i: top + 5.4 + 3.6 * i  # noqa: E731
x_mcu, x_dev = 24 + 30 + 4, 100 - 4
y_scl1, y_sda1 = pin_y(42, 0), pin_y(42, 1)
y2_scl, y2_sda = pin_y(30, 0), pin_y(30, 1)
y3_scl, y3_sda = pin_y(84, 0), pin_y(84, 1)
XB_SCL, XB_SDA = 76, 86
wire((x_mcu, y_scl1), (XB_SCL, y_scl1)); dot(XB_SCL, y_scl1)
wire((XB_SCL, y2_scl), (XB_SCL, y3_scl))
wire((XB_SCL, y2_scl), (x_dev, y2_scl)); wire((XB_SCL, y3_scl), (x_dev, y3_scl))
wire((x_mcu, y_sda1), (XB_SDA, y_sda1)); dot(XB_SDA, y_sda1)
wire((XB_SDA, y2_sda), (XB_SDA, y3_sda))
wire((XB_SDA, y2_sda), (x_dev, y2_sda)); wire((XB_SDA, y3_sda), (x_dev, y3_sda))
s.text(XB_SCL - 1.5, 66, "SCL", size=6, ha="right")
s.text(XB_SDA + 1.5, 66, "SDA", size=6, ha="left")

# ---- подтяжки SDA/SCL к +3,3 В (4,7 кОм) ----
s.part("R1", "R", XB_SCL, y2_scl - 20, "4,7 кОм", ("+3V3", "~SCL"), lab="l")
s.part("R2", "R", XB_SDA, y2_sda - 20, "4,7 кОм", ("+3V3", "~SDA"))
dot(XB_SCL, y2_scl); dot(XB_SDA, y2_sda)

# ---- общие шины питания и земли DD1 (выводы объединены линией) ----
xs_top = [24 + 30 * (i + 1) / 6 for i in range(5)]
wire((xs_top[0], 38), (xs_top[-1], 38))
for x in xs_top[1:-1]:
    dot(x, 38)
xs_bot = [24 + 30 * (i + 1) / 5 for i in range(4)]
wire((xs_bot[0], 64), (xs_bot[-1], 64))
for x in xs_bot[1:-1]:
    dot(x, 64)

# ---- кварц DS1307 ----
s.part("ZQ1", "XTAL", 62, 92, "32,768 кГц", ("XTAL1", "XTAL2"), lab="l")

# ---- развязывающие конденсаторы 0,1 мкФ ----
s.part("C1", "C", 146, 30, "0,1 мкФ", ("+3V3", "GND"))
s.part("C2", "C", 146, 84, "0,1 мкФ", ("+5V", "GND"))
s.part("C3", "C", 44, 84, "0,1 мкФ", ("+3V3", "GND"))

# ---- светодиод результата PA1 ----
s.part("R3", "R", 22, 100, "330 Ом", ("LED", "~LEDA"))
s.part("HL1", "LED", 22, 120, "LED-GREEN", ("~LEDA", "GND"))
s.text(12, 95, "светодиод результата (PA1)", size=5, style="italic")

s.text(12, 146, "Питание: DD1, DD2 — 3,3 В; DD3 — 5 В. SDA и SCL подтянуты к 3,3 В.", size=5.5)

expected = {
    "SCL": {"DD1/42", "DD2/6", "DD3/6", "R1/2"},
    "SDA": {"DD1/43", "DD2/5", "DD3/5", "R2/2"},
    "+3V3": {"DD1/7", "DD1/1", "DD1/9", "DD1/24", "DD1/36", "DD1/48", "DD2/8", "R1/1", "R2/1", "C1/1", "C3/1"},
    "+5V": {"DD3/8", "C2/1"},
    "GND": {"DD1/44", "DD1/23", "DD1/35", "DD1/47", "DD1/8", "DD2/1", "DD2/2", "DD2/3", "DD2/4", "DD2/7",
            "DD3/3", "DD3/4", "C1/2", "C2/2", "C3/2", "HL1/2"},
    "XTAL1": {"DD3/1", "ZQ1/1"},
    "XTAL2": {"DD3/2", "ZQ1/2"},
    "LED": {"DD1/11", "R3/1"},
    "LEDA": {"R3/2", "HL1/1"},
}
ok = s.check_nets(expected)
s.save(os.path.join(HERE, "pr2_i2c.png"), os.path.join(HERE, "pr2_i2c.pdf"))
sys.exit(0 if ok else 1)
