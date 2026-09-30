"""
Мини-генератор принципиальных схем KiCad (.kicad_sch) из Python.
Символы берутся из штатных библиотек KiCad и встраиваются в lib_symbols.
Правильность соединений проверяется не по картинке, а по нетлисту kicad-cli.
"""
import json
import math
import os
import re
import shutil
import subprocess
import uuid as _uuid
import xml.etree.ElementTree as ET

KICAD = os.path.expanduser("~/Applications/KiCad/KiCad.app/Contents")
KICAD_CLI = f"{KICAD}/MacOS/kicad-cli"
SYMDIR = f"{KICAD}/SharedSupport/symbols"

GREEN = (0, 150, 0)
BLUE = (0, 0, 160)  # остальные связи: у KiCad цвет провода по умолчанию тоже зелёный


def uid():
    return str(_uuid.uuid4())


# ---------- чтение библиотек ----------

def tokenize(text):
    return re.findall(r'"(?:[^"\\]|\\.)*"|\(|\)|[^\s()"]+', text)


def parse(tokens, i=0):
    out = []
    while i < len(tokens):
        t = tokens[i]
        if t == "(":
            sub, i = parse(tokens, i + 1)
            out.append(sub)
        elif t == ")":
            return out, i + 1
        else:
            out.append(t[1:-1] if t.startswith('"') else t)
            i += 1
    return out, i


def find_block(text, name):
    """Текст блока (symbol "name" ...) верхнего уровня в .kicad_sym."""
    m = re.search(r'\n\t\(symbol "%s"\n' % re.escape(name), text)
    if not m:
        raise KeyError(name)
    start = m.start() + 1
    depth, i = 0, start
    in_str = False
    while True:
        c = text[i]
        if in_str:
            if c == "\\":
                i += 1
            elif c == '"':
                in_str = False
        elif c == '"':
            in_str = True
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
        i += 1


_lib_cache = {}


def lib_symbol(lib, name):
    """-> (текст для lib_symbols с именем 'lib:name', {номер вывода: (x, y, угол, имя)})."""
    if lib not in _lib_cache:
        with open(f"{SYMDIR}/{lib}.kicad_sym", encoding="utf-8") as f:
            _lib_cache[lib] = f.read()
    block = find_block(_lib_cache[lib], name)
    if "(extends" in block.split("\n", 2)[1]:
        raise ValueError(f"{lib}:{name} наследуется — используйте базовый символ")
    block = block.replace(f'(symbol "{name}"', f'(symbol "{lib}:{name}"', 1)
    pins = {}
    tree, _ = parse(tokenize(block))

    def walk(node):
        if isinstance(node, list):
            if node and node[0] == "pin":
                at = next(x for x in node if isinstance(x, list) and x[0] == "at")
                num = next(x for x in node if isinstance(x, list) and x[0] == "number")[1]
                pname = next(x for x in node if isinstance(x, list) and x[0] == "name")[1]
                length = float(next(x for x in node if isinstance(x, list) and x[0] == "length")[1])
                pins.setdefault(num, (float(at[1]), float(at[2]), float(at[3]), pname, length))
            for x in node:
                walk(x)

    walk(tree)
    return block, pins


# ---------- модель схемы ----------

class Sheet:
    def __init__(self, project, title, paper="A3", portrait=False, date="", rev="", company="",
                 comments=(), sheet_layout=None):
        """comments для ГОСТ-рамки: [обозначение, разраб., пров., утв., т.контр., н.контр.]"""
        self.project = project
        self.root = uid()
        self.title, self.paper, self.portrait, self.date, self.rev = title, paper, portrait, date, rev
        self.company, self.comments, self.sheet_layout = company, comments, sheet_layout
        self.libs = {}
        self.items = []
        self.parts = {}

    def _lib(self, lib, name):
        key = f"{lib}:{name}"
        if key not in self.libs:
            self.libs[key] = lib_symbol(lib, name)
        return self.libs[key]

    def place(self, ref, lib, name, x, y, rot=0, value=None, mirror=None,
              ref_at=None, val_at=None, hide_ref=False, hide_val=False, footprint=""):
        _, pins = self._lib(lib, name)
        self.parts[ref] = dict(lib=f"{lib}:{name}", x=x, y=y, rot=rot, pins=pins,
                               value=value or name, mirror=mirror, ref_at=ref_at,
                               val_at=val_at, hide_ref=hide_ref, hide_val=hide_val,
                               footprint=footprint)
        return ref

    def pin(self, ref, num):
        """Абсолютные координаты конца вывода (точки подключения)."""
        p = self.parts[ref]
        px, py = p["pins"][str(num)][:2]
        if p["mirror"] == "y":
            px = -px
        elif p["mirror"] == "x":
            py = -py
        a = math.radians(p["rot"])
        rx = px * math.cos(a) - py * math.sin(a)
        ry = px * math.sin(a) + py * math.cos(a)
        return (round(p["x"] + rx, 2), round(p["y"] - ry, 2))

    def wire(self, *pts, color=None):
        pts = [tuple(round(c, 2) for c in pt) for pt in pts]
        for a, b in zip(pts, pts[1:]):
            if a != b:
                self.items.append(("wire", a, b, color))

    def route(self, a, b, color=None, first="h"):
        """Г-образное соединение a -> b."""
        if a[0] == b[0] or a[1] == b[1]:
            self.wire(a, b, color=color)
        elif first == "h":
            self.wire(a, (b[0], a[1]), b, color=color)
        else:
            self.wire(a, (a[0], b[1]), b, color=color)

    def junction(self, pt):
        self.items.append(("junction", pt))

    def label(self, text, pt, angle=0):
        self.items.append(("label", text, pt, angle))

    def no_connect(self, pt):
        self.items.append(("nc", pt))

    def text(self, s, pt, size=1.5):
        self.items.append(("text", s, pt, size))

    # ---------- сериализация ----------

    def _prop(self, name, val, x, y, hide=False, justify=None, angle=0):
        eff = "(effects (font (size 1.27 1.27))"
        if justify:
            eff += f" (justify {justify})"
        if hide:
            eff += " (hide yes)"
        eff += ")"
        return f'\t\t(property "{name}" "{val}" (at {x} {y} {angle}) {eff})\n'

    def render(self):
        o = ['(kicad_sch (version 20250114) (generator "eeschema") (generator_version "10.0")\n',
             f'\t(uuid "{self.root}")\n\t(paper "{self.paper}"{" portrait" if self.portrait else ""})\n',
             f'\t(title_block (title "{self.title}") (date "{self.date}") (rev "{self.rev}")'
             f' (company "{self.company}")'
             + "".join(f' (comment {i + 1} "{c}")' for i, c in enumerate(self.comments)) + ")\n",
             "\t(lib_symbols\n"]
        for block, _ in self.libs.values():
            o.append("\t" + block.replace("\n", "\n\t") + "\n")
        o.append("\t)\n")
        for it in self.items:
            kind = it[0]
            if kind == "wire":
                _, a, b, color = it
                color = color or BLUE
                col = f"(color {color[0]} {color[1]} {color[2]} 1)"
                o.append(f"\t(wire (pts (xy {a[0]} {a[1]}) (xy {b[0]} {b[1]}))"
                         f" (stroke (width 0) (type default) {col}) (uuid \"{uid()}\"))\n")
            elif kind == "junction":
                pt = it[1]
                o.append(f"\t(junction (at {pt[0]} {pt[1]}) (diameter 0) (color 0 0 0 0) (uuid \"{uid()}\"))\n")
            elif kind == "label":
                _, t, pt, ang = it
                just = "right bottom" if ang == 180 else "left bottom"
                o.append(f"\t(label \"{t}\" (at {pt[0]} {pt[1]} {ang}) (fields_autoplaced yes)"
                         f" (effects (font (size 1.27 1.27)) (justify {just})) (uuid \"{uid()}\"))\n")
            elif kind == "nc":
                pt = it[1]
                o.append(f"\t(no_connect (at {pt[0]} {pt[1]}) (uuid \"{uid()}\"))\n")
            elif kind == "text":
                _, s, pt, size = it
                o.append(f"\t(text \"{s}\" (exclude_from_sim no) (at {pt[0]} {pt[1]} 0)"
                         f" (effects (font (size {size} {size})) (justify left bottom)) (uuid \"{uid()}\"))\n")
        for ref, p in self.parts.items():
            x, y = p["x"], p["y"]
            mir = f" (mirror {p['mirror']})" if p["mirror"] else ""
            o.append(f'\t(symbol (lib_id "{p["lib"]}") (at {x} {y} {p["rot"]}){mir} (unit 1)'
                     f" (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no)"
                     f' (uuid "{uid()}")\n')
            rx, ry = p["ref_at"] or (x + 2.54, y - 2.54)
            vx, vy = p["val_at"] or (x + 2.54, y + 2.54)
            # KiCad поворачивает поля вместе с символом; компенсируем, чтобы текст был горизонтальным
            fa = p["rot"] % 180
            o.append(self._prop("Reference", ref, rx, ry, hide=p["hide_ref"], justify="left", angle=fa))
            o.append(self._prop("Value", p["value"], vx, vy, hide=p["hide_val"], justify="left", angle=fa))
            o.append(self._prop("Footprint", p["footprint"], x, y, hide=True))
            o.append(self._prop("Datasheet", "", x, y, hide=True))
            for num in p["pins"]:
                o.append(f'\t\t(pin "{num}" (uuid "{uid()}"))\n')
            o.append(f'\t\t(instances (project "{self.project}" (path "/{self.root}"'
                     f' (reference "{ref}") (unit 1))))\n\t)\n')
        o.append(f'\t(sheet_instances (path "/" (page "1")))\n)\n')
        return "".join(o)

    def save(self, directory):
        os.makedirs(directory, exist_ok=True)
        path = f"{directory}/{self.project}.kicad_sch"
        with open(path, "w", encoding="utf-8") as f:
            f.write(self.render())
        layout = ""
        if self.sheet_layout:
            layout = os.path.basename(self.sheet_layout)
            shutil.copy(f"{KICAD}/SharedSupport/template/{self.sheet_layout}", f"{directory}/{layout}")
        with open(f"{directory}/{self.project}.kicad_pro", "w") as f:
            json.dump({"meta": {"filename": f"{self.project}.kicad_pro", "version": 3},
                       "schematic": {"page_layout_descr_file": layout}}, f, indent=2)
        return path


# ---------- проверка ----------

def cli(*args):
    r = subprocess.run([KICAD_CLI, *args], capture_output=True, text=True)
    if r.returncode not in (0, 5):  # 5 — ERC нашёл нарушения, отчёт всё равно пишется
        raise RuntimeError(r.stdout + r.stderr)
    return r


def netlist(sch_path):
    out = sch_path.replace(".kicad_sch", ".net.xml")
    cli("sch", "export", "netlist", "--format", "kicadxml", "-o", out, sch_path)
    nets = {}
    for net in ET.parse(out).getroot().iter("net"):
        nets[net.get("name")] = {f'{n.get("ref")}/{n.get("pin")}' for n in net.iter("node")}
    os.remove(out)
    return nets


def check_nets(sch_path, expected):
    """expected: список множеств 'REF/pin', каждое множество — ровно одна цепь."""
    nets = netlist(sch_path)
    ok = True
    nets = {n: {x for x in v if not x.startswith("#")} for n, v in nets.items()}
    for group in expected:
        group = {x for x in group if not x.startswith("#")}
        found = [n for n, nodes in nets.items() if group <= nodes]
        if len(found) != 1:
            print(f"  [FAIL] нет цепи, объединяющей {sorted(group)}")
            ok = False
        elif nets[found[0]] != group:
            print(f"  [FAIL] цепь {found[0]}: ожидалось {sorted(group)}, есть {sorted(nets[found[0]])}")
            ok = False
        else:
            print(f"  [OK] {found[0]}: {' '.join(sorted(group))}")
    return ok, nets


def erc(sch_path):
    rpt = sch_path.replace(".kicad_sch", "-erc.rpt")
    cli("sch", "erc", "--severity-all", "-o", rpt, sch_path)
    with open(rpt, encoding="utf-8") as f:
        text = f.read()
    m = re.search(r"\*\* ERC messages: (\d+)\s+Errors (\d+)\s+Warnings (\d+)", text)
    return text, m.groups() if m else None


def export_png(sch_path, png_path, dpi=200, sheet_layout=None):
    d = os.path.dirname(sch_path)
    extra = ["--drawing-sheet", f"{d}/{os.path.basename(sheet_layout)}"] if sheet_layout else []
    cli("sch", "export", "pdf", "--no-background-color", *extra,
        "-o", f"{d}/_tmp.pdf", sch_path)
    base = png_path[:-4]
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", f"{d}/_tmp.pdf", base], check=True)
    os.replace(f"{d}/_tmp.pdf", sch_path.replace(".kicad_sch", ".pdf"))


def export_crop(pdf_path, png_path, inner_mm=(25, 10, 180, 215), dpi=300, pad_mm=4):
    """Кадр по содержимому схемы внутри рамки (inner_mm: x0, y0, x1, y1 в мм листа)."""
    from PIL import Image, ImageOps
    base = png_path[:-4] + "_full"
    subprocess.run(["pdftoppm", "-r", str(dpi), "-png", "-singlefile", pdf_path, base], check=True)
    img = Image.open(base + ".png").convert("L")
    k = dpi / 25.4
    x0, y0, x1, y1 = (int(v * k) for v in inner_mm)
    inner = img.crop((x0, y0, x1, y1))
    bx0, by0, bx1, by1 = ImageOps.invert(inner).point(lambda v: 255 if v > 40 else 0).getbbox()
    pad = int(pad_mm * k)
    box = (max(x0 + bx0 - pad, 0), max(y0 + by0 - pad, 0), x0 + bx1 + pad, y0 + by1 + pad)
    Image.open(base + ".png").crop(box).save(png_path)
    os.remove(base + ".png")
