"""Принципиальные схемы ПР2 (внешние ОЗУ и ПЗУ для МК-51) и проверка списка цепей.

Запуск: python3 draw.py  -> schematics/pr2_ram.png|pdf (ПР2.ПЭПС.003 Э3), schematics/pr2_rom.png|pdf (ПР2.ПЭПС.004 Э3).
Соединения заданы именами цепей (как метки цепей в Multisim); шины Bus1 (AD0-AD7) и Bus2 (A0-A12)
показаны утолщёнными линиями с ответвлениями. Расчёт цепей из тех же данных сверяется с ожидаемым
списком (Sheet.check_nets), скрипт завершается с ошибкой, если есть расхождения.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "tools"))
import matplotlib.pyplot as plt  # noqa: E402
from schem import Sheet  # noqa: E402

plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Serif"]
OUT = os.path.join(HERE, "schematics")


class PR2Sheet(Sheet):
    """Sheet, у которого цепи шин рисуются не метками у выводов, а ответвлениями к шине."""

    def __init__(self, *a, bus_nets=(), **kw):
        super().__init__(*a, **kw)
        self.bus_nets = set(bus_nets)
        self.ends = []                      # (цепь, x, y, сторона)

    def _label(self, net, x, y, side):
        if net in self.bus_nets and side in ("l", "r"):
            self.ends.append((net, x, y, side))
            return
        super()._label(net, x, y, side)

    def bus_bar(self, name, x_ends, bar_x, nets=None, label_side=1, label_dy=0.0):
        """Ответвления от выводов (x_ends - абсциссы концов выводов) к вертикальной шине в bar_x."""
        pts = [e for e in self.ends if any(abs(e[1] - xe) < 0.01 for xe in x_ends)
               and (nets is None or e[0] in nets)]
        ys = []
        for net, x, y, side in pts:
            self.ax.plot([x, bar_x], [y, y], color="#006400", lw=0.35)
            self.ax.text((x + bar_x) / 2, y - 0.5, net, ha="center", va="bottom", fontsize=4.4)
            ys.append(y)
        y0, y1 = min(ys), max(ys)
        self.ax.plot([bar_x, bar_x], [y0 - 1, y1 + 1], color="black", lw=1.8, solid_capstyle="butt")
        self.ax.text(bar_x, y0 - 2.2, name, ha="center", va="bottom", fontsize=6, fontweight="bold")


def build(kind):
    ram = kind == "ram"
    code = "ПР2.ПЭПС.003 Э3" if ram else "ПР2.ПЭПС.004 Э3"
    title = ("Подключение внешнего ОЗУ 8Кx8 к МК-51. Схема электрическая принципиальная" if ram else
             "Подключение внешнего ПЗУ 8Кx8 к МК-51. Схема электрическая принципиальная")
    bus = [f"AD{i}" for i in range(8)] + [f"A{i}" for i in range(13)]
    s = PR2Sheet(160, 172, title="", code=code, author="Васин С.А.", group="ЭФБО-17-24", bus_nets=bus)

    # ---- DD1: МК-51 (КМ1816ВЕ51 / AT89C51), DIP-40 ----
    p0 = [(39 - i, f"P0.{i}/AD{i}", f"AD{i}") for i in range(8)]
    p2 = [(28, "P2.7", ""), (27, "P2.6", ""), (26, "P2.5", "")] + \
         [(25 - i, f"P2.{4 - i}/A{12 - i}", f"A{12 - i}") for i in range(5)]
    left1 = [(1, "P1.0", "LED")] + [(1 + i, f"P1.{i}", "") for i in range(1, 8)] + [(9, "RST", "RST")] + \
            [(10 + i, f"P3.{i}", "") for i in range(6)] + \
            [(16, "P3.6/WR", "WR" if ram else ""), (17, "P3.7/RD", "RD"),
             (18, "XTAL2", "XTAL2"), (19, "XTAL1", "XTAL1")]
    right1 = p0 + [(31, "EA", "+5V"), (30, "ALE", "ALE"), (29, "PSEN", "")] + p2
    s.ic("DD1", "МК-51 (8051), DIP-40", 24, 16, 22, left=left1, right=right1,
         top=[(40, "VCC", "+5V")], bottom=[(20, "GND", "GND")])

    # ---- DD2: регистр-защёлка 74LS373 ----
    d_pins = [3, 4, 7, 8, 13, 14, 17, 18]
    q_pins = [2, 5, 6, 9, 12, 15, 16, 19]
    left2 = [(d_pins[i], f"D{i}", f"AD{i}") for i in range(8)] + [(11, "LE", "ALE")]
    right2 = [(q_pins[i], f"Q{i}", f"A{i}") for i in range(8)]
    s.ic("DD2", "74LS373", 76, 26, 18, left=left2, right=right2,
         top=[(20, "VCC", "+5V")], bottom=[(1, "OE#", "GND"), (10, "GND", "GND")])

    # ---- DD3: память 8Кx8 ----
    a_pins = [10, 9, 8, 7, 6, 5, 4, 3, 25, 24, 21, 23, 2]
    dm = [11, 12, 13, 15, 16, 17, 18, 19]
    left3 = [(a_pins[i], f"A{i}", f"A{i}") for i in range(13)]
    if ram:
        right3 = [(dm[i], f"D{i}", f"AD{i}") for i in range(8)] + [(22, "G#(OE)", "RD"), (27, "W#(WE)", "WR")]
        top3, bot3 = [(28, "VCC", "+5V"), (26, "E2", "+5V")], [(14, "GND", "GND"), (20, "E1#", "GND")]
        s.ic("DD3", "HM-65642 (6264), 8Кx8 ОЗУ", 120, 34, 20, left=left3, right=right3, top=top3, bottom=bot3)
    else:
        right3 = [(dm[i], f"O{i}", f"AD{i}") for i in range(8)] + [(22, "OE#", "RD"), (27, "PGM#", "+5V")]
        top3, bot3 = [(28, "VCC", "+5V"), (1, "VPP", "+5V")], [(14, "GND", "GND"), (20, "CE#", "GND")]
        s.ic("DD3", "27C64, 8Кx8 ПЗУ (EPROM)", 120, 34, 20, left=left3, right=right3, top=top3, bottom=bot3)

    # ---- шины ----
    s.bus_bar("Bus1", [50, 72], 61, nets={f"AD{i}" for i in range(8)}, label_side=1)
    s.bus_bar("Bus1", [144], 150, nets={f"AD{i}" for i in range(8)}, label_side=1)
    s.bus_bar("Bus2", [50], 57, nets={f"A{i}" for i in range(8, 13)}, label_side=1)
    s.bus_bar("Bus2", [98, 116], 106, nets={f"A{i}" for i in range(13)}, label_side=-1)

    # ---- внешние элементы ----
    y = 114
    s.part("ZQ1", "XTAL", 18, y, "12 МГц", ("XTAL1", "XTAL2"))
    s.part("C1", "C", 38, y, "30 пФ", ("XTAL1", "GND"))
    s.part("C2", "C", 58, y, "30 пФ", ("XTAL2", "GND"))
    s.part("C3", "C", 80, y, "10 мкФ", ("+5V", "RST"))
    s.part("R1", "R", 100, y, "8,2 кОм", ("RST", "GND"))
    s.part("R2", "R", 120, y, "330 Ом", ("LED", "N1"))
    s.part("HL1", "LED", 138, y, "АЛ307", ("N1", "GND"))
    s.text(61, 105, "Bus1 - AD0-AD7 (мультиплексированная шина адрес/данные), "
                    "Bus2 - A0-A12 (адрес внешней памяти).\nОдноимённые цепи и шины соединены.", 4.6)
    s.text(74, 147 + 11.2, title.split(". ")[0], 6.5, va="center")
    s.text(74, 147 + 15.2, "Схема электрическая принципиальная", 6.5, va="center")

    exp = expected(ram)
    print(f"схема {code}:")
    ok = s.check_nets(exp)
    if not ok:
        sys.exit(1)
    name = f"pr2_{kind}"
    s.save(os.path.join(OUT, name + ".png"), os.path.join(OUT, name + ".pdf"))
    return s


def expected(ram):
    e = {}
    for i in range(8):
        e[f"AD{i}"] = {f"DD1/{39 - i}", f"DD2/{[3, 4, 7, 8, 13, 14, 17, 18][i]}", f"DD3/{[11, 12, 13, 15, 16, 17, 18, 19][i]}"}
        e[f"A{i}"] = {f"DD2/{[2, 5, 6, 9, 12, 15, 16, 19][i]}", f"DD3/{[10, 9, 8, 7, 6, 5, 4, 3][i]}"}
    for k, (p1, p3) in enumerate(zip(range(21, 26), [25, 24, 21, 23, 2])):
        e[f"A{8 + k}"] = {f"DD1/{p1}", f"DD3/{p3}"}
    e["ALE"] = {"DD1/30", "DD2/11"}
    e["RD"] = {"DD1/17", "DD3/22"}
    if ram:
        e["WR"] = {"DD1/16", "DD3/27"}
    e["LED"] = {"DD1/1", "R2/1"}
    e["N1"] = {"R2/2", "HL1/1"}
    e["RST"] = {"DD1/9", "C3/2", "R1/1"}
    e["XTAL1"] = {"DD1/19", "ZQ1/1", "C1/1"}
    e["XTAL2"] = {"DD1/18", "ZQ1/2", "C2/1"}
    vcc = {"DD1/40", "DD1/31", "DD2/20", "DD3/28", "C3/1"}
    vcc |= {"DD3/26"} if ram else {"DD3/1", "DD3/27"}
    e["+5V"] = vcc
    e["GND"] = {"DD1/20", "DD2/10", "DD2/1", "DD3/14", "DD3/20", "C1/2", "C2/2", "R1/2", "HL1/2"}
    return e


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    build("ram")
    build("rom")
