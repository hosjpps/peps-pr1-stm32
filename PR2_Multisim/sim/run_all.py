"""Прогон тестов в симуляторе uCsim (s51, пакет SDCC) на частоте 12 МГц.

Запуск: python3 run_all.py   (предварительно: sh ../firmware/build.sh)
s51 запускается с сетевой консолью (-Z), скрипт отправляет команды и читает ответы.
Каждый прогон пишет лог sim/*.log (команда -> вывод uCsim), общие итоги - results.json.
Модель внешней памяти в uCsim - xram (64 Кбайт, при старте заполнена случайными числами,
seed фиксирован ключом -R). Светодиод HL1 - бит P1.0 (SFR 0x90).
"""
import json
import os
import re
import socket
import subprocess
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FW = os.path.join(HERE, "..", "firmware")
BUILD = os.path.join(FW, "build")
ZZZ, K, CELLS = 0x0800, 100, 1024
PROMPT = "@@> "
PORT = 47200


class Sim:
    """Один сеанс s51: команда -> текст ответа; весь обмен копится в self.log."""

    def __init__(self, ihx, title):
        global PORT
        PORT += 1
        self.log = [f"# {title}", f"# s51 -t 8051 -X 12M -R 1 build/{ihx}  (команды вводятся в консоль uCsim)"]
        self.p = subprocess.Popen(
            ["s51", "-q", "-t", "8051", "-X", "12M", "-R", "1", "-Z", str(PORT), "-p", PROMPT,
             os.path.join(BUILD, ihx)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(50):
            try:
                self.s = socket.create_connection(("127.0.0.1", PORT))
                break
            except OSError:
                time.sleep(0.1)
        self.s.settimeout(60)
        self._read()

    def _read(self):
        buf = b""
        while not buf.endswith(PROMPT.encode()):
            buf += self.s.recv(65536)
        buf = re.sub(rb"\xff[\xfb-\xfe].", b"", buf).replace(b"\x00", b"").decode("utf-8", "replace")
        return buf.replace("\r", "")

    def cmd(self, c):
        self.s.sendall((c + "\n").encode())
        out = self._read()
        lines = out.split("\n")
        if lines and lines[0].strip() == c.strip():     # убрать эхо команды
            lines = lines[1:]
        body = "\n".join(lines)
        body = re.sub(r"\d*" + re.escape(PROMPT) + r"$", "", body).rstrip("\n")
        short = c if len(c) < 90 else c[:80] + " ... (всего %d значений)" % len(c.split()[3:])
        self.log.append(f"s51> {short}")
        if body:
            self.log.append(body)
        return body

    def close(self, name):
        self.s.sendall(b"quit\n")
        self.s.close()
        self.p.terminate()
        self.p.wait()
        with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
            f.write("\n".join(self.log) + "\n")


def addr_end(lst, base=0xAA):
    """Адрес команды `while(1);` (последний sjmp в main) по листингу SDCC; base - адрес main из .map."""
    text = open(lst, encoding="utf-8").read().split("_main:")[1]
    offs = re.findall(r"^\s+([0-9A-F]{6}) [0-9A-F]{2} [0-9A-F]{2}\s+\[24\]\s+\d+\s+\tsjmp", text, re.M)
    return base + int(offs[-1], 16)


def clks(state_out):
    return int(re.search(r"\((\d+) clks\)", state_out.split("Total time")[1]).group(1))


def cells(out):
    d = {}
    for ln in out.splitlines():
        m = re.match(r"^0x([0-9a-f]{4})((?: [0-9a-f]{2}| {3})+)", ln)
        if m:
            for i, h in enumerate(re.findall(r"[0-9a-f]{2}", m.group(2))):
                d[int(m.group(1), 16) + i] = int(h, 16)
    return d


def iram(out):
    m = re.match(r"^0x[0-9a-f]{2} ((?:[0-9a-f]{2} ?)+)", out.strip())
    return [int(x, 16) for x in m.group(1).split()]


results = {}


def run_ram(name, ihx, title, xx, fault=False):
    end = addr_end(os.path.join(BUILD, ihx.replace(".ihx", ".lst")))
    sim = Sim(ihx, title)
    before = cells(sim.cmd("dx 0x7f8 0x7ff")) | cells(sim.cmd("dx 0xc00 0xc07"))
    sim.cmd(f"break 0x{end:04x}")
    if fault:
        # имитация неисправной ячейки: перед чтением 100-й ячейки (0863h) искажаем её содержимое
        sim.cmd("break 0x00cd 100")
        sim.cmd("run")
        sim.cmd("dx 0x862 0x864")
        sim.cmd("set memory xram 0x863 0xab")
        sim.cmd("dx 0x862 0x864")
        sim.cmd("delete 2")
    sim.cmd("run")
    st = sim.cmd("state")
    sim.cmd("info registers")
    v = iram(sim.cmd("di 0x08 0x0c"))
    p1 = iram(sim.cmd("ds 0x90 0x90"))[0]
    after = cells(sim.cmd("dx 0x7f8 0x7ff")) | cells(sim.cmd("dx 0xc00 0xc07"))
    area = cells(sim.cmd(f"dx 0x{ZZZ:04x} 0x{ZZZ + CELLS - 1:04x}"))
    sim.close(name)
    n = sum(area[a] == xx for a in range(ZZZ, ZZZ + CELLS))
    results[name] = {"xx": xx, "cycles": clks(st) // 12, "time_ms": round(clks(st) / 12e6 * 1000, 3),
                     "cells_equal_xx": n, "outside_unchanged": before == after,
                     "result": v[0], "checked": v[1] | v[2] << 8, "error_addr": v[3] | v[4] << 8,
                     "p1": p1, "p1_0": p1 & 1}
    print(name, results[name])


def run_rom(name, ihx, title, image):
    end = addr_end(os.path.join(BUILD, ihx.replace(".ihx", ".lst")))
    sim = Sim(ihx, title)
    sim.cmd(f"set memory xram 0x{ZZZ:04x} " + " ".join(f"0x{b:02x}" for b in image))
    sim.cmd(f"dx 0x{ZZZ:04x} 0x{ZZZ + K - 1:04x}")
    sim.cmd(f"break 0x{end:04x}")
    sim.cmd("run")
    st = sim.cmd("state")
    sim.cmd("info registers")
    v = iram(sim.cmd("di 0x08 0x09"))
    p1 = iram(sim.cmd("ds 0x90 0x90"))[0]
    sim.close(name)
    results[name] = {"sum_image": sum(image) & 0xFF, "cycles": clks(st) // 12,
                     "time_ms": round(clks(st) / 12e6 * 1000, 3), "result": v[0], "calc_sum": v[1],
                     "p1": p1, "p1_0": p1 & 1}
    print(name, results[name])


def run_trace(name, ihx, title, loop_start, load=None, nsteps=40):
    """Трасса одной итерации цикла: по каждой команде - адрес, мнемоника, число машинных циклов."""
    sim = Sim(ihx, title)
    if load:
        sim.cmd(load)
    sim.cmd(f"break 0x{loop_start:04x} 3")      # на 3-й итерации, когда цикл уже «разогнан»
    sim.cmd("run")
    sim.cmd("delete 1")
    sim.cmd("history clear")
    t = [clks(sim.cmd("state"))]
    for _ in range(nsteps):
        sim.cmd("step 1")
        t.append(clks(sim.cmd("state")))
    hist = sim.cmd(f"history list {nsteps}")
    sim.close(name)
    ins = re.findall(r"^0x([0-9a-f]{4})\s+(?:[0-9a-f]{2} ?)+\s+([A-Z].*?)\s*$", hist, re.M)
    seq = []
    for k, (a, m) in enumerate(ins):
        if k and int(a, 16) == loop_start:
            break
        seq.append({"addr": int(a, 16), "op": " ".join(m.split()), "cycles": (t[k + 1] - t[k]) // 12})
    results[name.replace(".log", "")] = {"loop": seq, "cycles_total": sum(s["cycles"] for s in seq)}
    print(name, len(seq), "команд,", sum(s["cycles"] for s in seq), "машинных циклов")


if __name__ == "__main__":
    image_ok = open(os.path.join(FW, "rom_image.bin"), "rb").read()
    run_ram("ram_test_AA.log", "ram_test.ihx", "Задание 1: ОЗУ, XX=0AAh, 1024 ячейки с 0800h", 0xAA)
    run_ram("ram_test_55.log", "ram_test_55.ihx", "Задание 1: ОЗУ, XX=55h (параметр сменён ключом -DTEST_BYTE=0x55)", 0x55)
    run_ram("ram_test_fault.log", "ram_test.ihx",
            "Задание 1: ОЗУ, имитация неисправной ячейки 0863h (содержимое искажено перед чтением)", 0xAA, fault=True)
    run_rom("rom_test_ok.log", "rom_test.ihx", "Задание 2: ПЗУ, образ без искажений", image_ok)
    bad = bytearray(image_ok)
    bad[0x10] ^= 0x01
    run_rom("rom_test_fault.log", "rom_test.ihx",
            "Задание 2: ПЗУ, имитация неисправности: байт по адресу 0810h искажён (бит 0)", bytes(bad))
    run_trace("trace_ram.log", "ram_test.ihx", "Трасса одной итерации цикла теста ОЗУ (адрес 00C2h - начало цикла)", 0x00C2)
    run_trace("trace_rom.log", "rom_test.ihx", "Трасса одной итерации цикла контрольной суммы ПЗУ (адрес 00B4h - начало цикла)",
              0x00B4, load="set memory xram 0x0800 " + " ".join(f"0x{b:02x}" for b in image_ok))
    with open(os.path.join(HERE, "results.json"), "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=1)
