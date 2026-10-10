"""
Принципиальные схемы без KiCad: микросхемы рисуются прямоугольниками, соединения задаются
именами цепей (как метки цепей в Eeschema/Multisim). Рисунок строится из того же списка цепей,
по которому его можно проверить (nets()/check_nets()).

    s = Sheet(160, 230, title=..., code="ПР2.ПЭПС.003 Э3", author="Васин С.А.")
    u1 = s.ic("DD1", "AT89C51", 20, 20, w=34,
              left=[(1, "P1.0", "LED"), ...], right=[...], top=[...], bottom=[...])
    r = s.part("R1", "R", 100, 50, "4,7k", ("SCL", "+3V3"), orient="v")
    s.save("out.png")
Пин — (номер, имя внутри корпуса, цепь). Цепь "" — не подключён, "GND" и "+5V"/"+3V3" рисуются
символами земли и питания.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

PITCH = 3.6      # мм между выводами
STUB = 4.0       # длина вывода
LINE = 0.25
FONT = 5.2
COLOR = "#7a0000"
GREEN = "#006400"


class Sheet:
    def __init__(self, w, h, title="", code="", author="", group="", org="РТУ МИРЭА", scale="1:1",
                 lit=""):
        self.w, self.h = w, h
        self.fig = plt.figure(figsize=(w / 25.4, h / 25.4))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, w)
        self.ax.set_ylim(h, 0)
        self.ax.axis("off")
        self.parts = {}
        self.title, self.code, self.author, self.group, self.org = title, code, author, group, org
        self._frame()

    # ---------- рамка и основная надпись (упрощённая форма 2 ГОСТ 2.104) ----------
    def _frame(self):
        a, w, h = self.ax, self.w, self.h
        a.add_patch(Rectangle((8, 3), w - 11, h - 6, fill=False, lw=0.8, ec="black"))
        x0, y0 = w - 3 - 110, h - 3 - 22
        a.add_patch(Rectangle((x0, y0), 110, 22, fill=False, lw=0.6, ec="black"))
        for x in (x0 + 25,):
            a.plot([x, x], [y0, y0 + 22], "k", lw=0.4)
        a.plot([x0, x0 + 110], [y0 + 8, y0 + 8], "k", lw=0.4)
        a.plot([x0 + 25, x0 + 25], [y0 + 8, y0 + 22], "k", lw=0.4)
        a.text(x0 + 55, y0 + 4, self.code, ha="center", va="center", fontsize=9)
        a.text(x0 + 2, y0 + 12, self.title, ha="left", va="center", fontsize=6.5, wrap=True)
        a.text(x0 + 2, y0 + 19, "Разраб.", fontsize=5, va="center")
        a.text(x0 + 12.5, y0 + 19, self.author, fontsize=5.5, va="center")
        a.text(x0 + 70, y0 + 19, f"{self.org}, {self.group}" if self.group else self.org,
               fontsize=5.5, va="center")

    # ---------- элементы ----------
    def _sym(self, kind, x, y, pos):
        """Символ цепи на конце вывода: земля, питание, «не подключено»."""
        a = self.ax
        if kind == "GND":
            a.plot([x, x], [y, y + 1.5], color=GREEN, lw=LINE * 1.4)
            for i, half in enumerate((2.6, 1.7, 0.8)):
                a.plot([x - half, x + half], [y + 1.5 + i * 0.9] * 2, color=COLOR, lw=0.5)
        elif kind.startswith("+") or kind in ("VCC", "VDD"):
            a.plot([x, x], [y, y - 1.8], color=GREEN, lw=LINE * 1.4)
            a.plot([x - 1.5, x + 1.5], [y - 1.8] * 2, color=COLOR, lw=0.6)
            a.text(x, y - 2.8, kind.replace(".", ","), ha="center", va="bottom", fontsize=FONT)

    def _label(self, net, x, y, side):
        """Метка цепи у конца вывода; side: 'l','r','t','b' — куда направлена."""
        if net.startswith("~"):
            return
        if not net or net == "NC":
            if net == "NC":
                d = 0.9
                self.ax.plot([x - d, x + d], [y - d, y + d], color=COLOR, lw=0.6)
                self.ax.plot([x - d, x + d], [y + d, y - d], color=COLOR, lw=0.6)
            return
        if (net == "GND" or net.startswith("+") or net in ("VCC", "VDD")) and side in ("t", "b"):
            self._sym(net, x, y, side)
            return
        if side == "l":
            self.ax.text(x - 0.8, y, net, ha="right", va="center", fontsize=FONT, color="black")
        elif side == "r":
            self.ax.text(x + 0.8, y, net, ha="left", va="center", fontsize=FONT, color="black")
        elif side == "t":
            self.ax.text(x, y - 0.8, net, ha="center", va="bottom", fontsize=FONT, rotation=90)
        else:
            self.ax.text(x, y + 0.8, net, ha="center", va="top", fontsize=FONT, rotation=90)

    def ic(self, ref, value, x, y, w, left=(), right=(), top=(), bottom=(), pad=PITCH * 1.5,
           name_inside=True):
        """Микросхема: левый верхний угол (x, y), ширина w. Возвращает ref."""
        n = max(len(left), len(right))
        h = (n - 1) * PITCH + 2 * pad if n else 2 * pad
        a = self.ax
        a.add_patch(Rectangle((x, y), w, h, fill=True, fc="#fffbe0", lw=0.7, ec=COLOR))
        a.text(x, y - 1.0, ref, ha="left", va="bottom", fontsize=6.5)
        a.text(x, y + h + (STUB + 4.0 if bottom else 1.0), value, ha="left", va="top", fontsize=6)
        pins = {}

        def side_pins(lst, side):
            for i, (num, nm, net) in enumerate(lst):
                py = y + pad + i * PITCH
                if side == "l":
                    x1, x0 = x - STUB, x
                    a.plot([x1, x0], [py, py], color=GREEN if net else COLOR, lw=LINE * 1.4)
                    a.text(x + 0.8, py, nm, ha="left", va="center", fontsize=FONT)
                    a.text(x - 1, py - 0.5, str(num), ha="right", va="bottom", fontsize=4.2, color=COLOR)
                    self._label(net, x1, py, "l")
                    pins[num] = (nm, net)
                else:
                    x0, x1 = x + w, x + w + STUB
                    a.plot([x0, x1], [py, py], color=GREEN if net else COLOR, lw=LINE * 1.4)
                    a.text(x + w - 0.8, py, nm, ha="right", va="center", fontsize=FONT)
                    a.text(x + w + 1, py - 0.5, str(num), ha="left", va="bottom", fontsize=4.2, color=COLOR)
                    self._label(net, x1, py, "r")
                    pins[num] = (nm, net)

        side_pins(left, "l")
        side_pins(right, "r")
        for lst, side in ((top, "t"), (bottom, "b")):
            if not lst:
                continue
            step = w / (len(lst) + 1)
            for i, (num, nm, net) in enumerate(lst):
                px = x + step * (i + 1)
                if side == "t":
                    a.plot([px, px], [y - STUB, y], color=GREEN if net else COLOR, lw=LINE * 1.4)
                    a.text(px - 0.5, y + 0.8, nm, ha="right", va="top", fontsize=FONT, rotation=90)
                    a.text(px + 0.4, y - STUB / 2, str(num), ha="left", va="center", fontsize=4.2,
                           color=COLOR)
                    self._label(net, px, y - STUB, "t")
                else:
                    a.plot([px, px], [y + h, y + h + STUB], color=GREEN if net else COLOR, lw=LINE * 1.4)
                    a.text(px - 0.5, y + h - 0.8, nm, ha="right", va="bottom", fontsize=FONT, rotation=90)
                    a.text(px + 0.4, y + h + STUB / 2, str(num), ha="left", va="center", fontsize=4.2,
                           color=COLOR)
                    self._label(net, px, y + h + STUB, "b")
                pins[num] = (nm, net)
        self.parts[ref] = pins
        return ref

    def part(self, ref, kind, x, y, value, nets, orient="v", lab="r"):
        """Двухвыводной элемент: R, C, LED, XTAL. nets = (цепь у вывода 1, цепь у вывода 2)."""
        a = self.ax
        L = 7.0
        if orient == "v":
            a.plot([x, x], [y, y + L], color=GREEN, lw=LINE * 1.4)
            a.plot([x, x], [y + L + 6, y + 2 * L + 6], color=GREEN, lw=LINE * 1.4)
            cy = y + L + 3
            if kind == "R":
                a.add_patch(Rectangle((x - 1.5, y + L), 3, 6, fill=False, lw=0.6, ec=COLOR))
            elif kind == "C":
                a.plot([x - 2.2, x + 2.2], [cy - 0.7] * 2, color=COLOR, lw=0.8)
                a.plot([x - 2.2, x + 2.2], [cy + 0.7] * 2, color=COLOR, lw=0.8)
            elif kind == "LED":
                a.fill([x - 2, x + 2, x], [cy - 2, cy - 2, cy + 2], fc="white", ec=COLOR, lw=0.6)
                a.plot([x - 2, x + 2], [cy + 2] * 2, color=COLOR, lw=0.8)
            elif kind == "XTAL":
                a.add_patch(Rectangle((x - 1.2, y + L + 0.5), 2.4, 5, fill=False, lw=0.6, ec=COLOR))
                a.plot([x - 2.4, x + 2.4], [y + L + 0.2] * 2, color=COLOR, lw=0.8)
                a.plot([x - 2.4, x + 2.4], [y + L + 5.8] * 2, color=COLOR, lw=0.8)
            lx, ha = (x + 3.5, "left") if lab == "r" else (x - 3.5, "right")
            a.text(lx, cy - 1.2, ref, fontsize=6, va="center", ha=ha)
            a.text(lx, cy + 1.6, value, fontsize=5.5, va="center", ha=ha)
            self._label(nets[0], x, y, "t")
            self._label(nets[1], x, y + 2 * L + 6, "b")
        else:
            a.plot([x, x + L], [y, y], color=GREEN, lw=LINE * 1.4)
            a.plot([x + L + 6, x + 2 * L + 6], [y, y], color=GREEN, lw=LINE * 1.4)
            if kind == "R":
                a.add_patch(Rectangle((x + L, y - 1.5), 6, 3, fill=False, lw=0.6, ec=COLOR))
            a.text(x + L + 3, y - 3.2, ref, fontsize=6, ha="center")
            a.text(x + L + 3, y + 4.2, value, fontsize=5.5, ha="center")
            self._label(nets[0], x, y, "l")
            self._label(nets[1], x + 2 * L + 6, y, "r")
        self.parts[ref] = {1: (kind, nets[0]), 2: (kind, nets[1])}
        return ref

    def text(self, x, y, s, size=6, **kw):
        self.ax.text(x, y, s, fontsize=size, **kw)

    def bus(self, x0, y0, x1, y1, label):
        """Условное обозначение шины: утолщённая линия и подпись."""
        self.ax.plot([x0, x1], [y0, y1], color="black", lw=1.6)
        self.ax.text((x0 + x1) / 2, (y0 + y1) / 2 - 1.2, label, fontsize=6, ha="center", va="bottom")

    # ---------- список цепей и проверка ----------
    def nets(self):
        out = {}
        for ref, pins in self.parts.items():
            for num, v in pins.items():
                net = v[1].lstrip("~")
                if net and net != "NC":
                    out.setdefault(net, set()).add(f"{ref}/{num}")
        return out

    def check_nets(self, expected):
        """expected: {цепь: {'REF/pin', ...}}; печатает расхождения, возвращает True/False."""
        got, ok = self.nets(), True
        for net, pins in expected.items():
            if got.get(net) != set(pins):
                ok = False
                print(f"  [FAIL] {net}: ожидалось {sorted(pins)}, есть {sorted(got.get(net, []))}")
            else:
                print(f"  [OK] {net}: {' '.join(sorted(pins))}")
        for net in got.keys() - expected.keys():
            ok = False
            print(f"  [FAIL] лишняя цепь {net}: {sorted(got[net])}")
        return ok

    def save(self, png, pdf=None, dpi=250):
        self.fig.savefig(png, dpi=dpi)
        if pdf:
            self.fig.savefig(pdf)
        plt.close(self.fig)
