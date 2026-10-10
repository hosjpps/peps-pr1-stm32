"""Осциллограммы ALE (и RD/WR/PSEN) по модели на основе трассы выполнения из uCsim.

Multisim недоступен на macOS, поэтому картинка строится не снимком прибора, а по модели:
  - частота кварца 12 МГц, машинный цикл 1 мкс (12 периодов);
  - ALE формируется 2 раза за машинный цикл (период 0,5 мкс): импульсы начинаются на 1/12 и 7/12 мкс
    цикла (S1P2 и S4P2), ширина импульса принята равной половине периода ALE (0,25 мкс) по виду рис. 28;
  - при каждом обращении MOVX один импульс ALE пропускается (первый импульс второго цикла команды);
  - в этом цикле активен строб RD (чтение) или WR (запись): низкий уровень 6 периодов (0,5 мкс);
  - программа выполняется из резидентного ПЗУ (EA = +5 В), поэтому PSEN остаётся неактивным.
Последовательность команд и число машинных циклов каждой берутся из sim/results.json (трасса s51).
Запуск: python3 scope.py  (после sim/run_all.py)
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.family"] = ["Times New Roman", "DejaVu Serif"]
HERE = os.path.dirname(os.path.abspath(__file__))
ALE_W = 0.25            # ширина импульса ALE, мкс (половина периода 0,5 мкс)
ALE_AT = (1 / 12, 7 / 12)
STROBE = (1 / 12, 7 / 12)   # RD/WR: низкий уровень от 1/12 до 7/12 мкс второго цикла MOVX


def timeline(loop):
    """Возвращает ({сигнал: [(t0, t1) интервалы активного уровня]}, [(t0, t1, текст)], t_всего)."""
    ale, rd, wr, ins = [], [], [], []
    t = 0.0
    for s in loop:
        op, c = s["op"], s["cycles"]
        ins.append((t, t + c, op))
        movx = op.startswith("MOVX")
        for j in range(c):
            tc = t + j
            if movx and j == 1:
                (wr if "@DPTR,A" in op.replace(" ", "") else rd).append((tc + STROBE[0], tc + STROBE[1]))
            for k, a in enumerate(ALE_AT):
                if movx and j == 1 and k == 0:
                    continue             # пропущенный импульс ALE
                ale.append((tc + a, tc + a + ALE_W))
        t += c
    return {"ALE": ale, "RD": rd, "WR": wr}, ins, t


def wave(intervals, t_end, active_high):
    xs, ys = [0.0], [0.0 if active_high else 5.0]
    hi, lo = (5.0, 0.0) if active_high else (0.0, 5.0)
    for a, b in sorted(intervals):
        xs += [a, a, b, b]
        ys += [lo, hi, hi, lo]
    xs.append(t_end)
    ys.append(lo)
    return xs, ys


def draw(name, loop, start, extra, title):
    sig, ins, total = timeline(loop)
    win = (start, start + 10.0)
    fig = plt.figure(figsize=(160 / 25.4, 112 / 25.4))
    n = 1 + len(extra)
    top, bottom = 0.86, 0.12
    h = (top - bottom) / n
    # полоса с командами
    axi = fig.add_axes([0.10, top + 0.005, 0.86, 0.09])
    axi.set_xlim(*win)
    axi.set_ylim(0, 1)
    axi.axis("off")
    for t0, t1, op in ins:
        if t1 <= win[0] or t0 >= win[1]:
            continue
        axi.add_patch(plt.Rectangle((t0, 0.05), t1 - t0, 0.9, fill=True, fc="#eef3fb", ec="#555", lw=0.5))
        txt = op.replace("0x82 <DPL>", "DPL").replace("0x83 <DPH>", "DPH").replace("0x0d", "nabor")
        txt = txt.replace("0x06 <R6>", "R6").replace("0x07 <R7>", "R7").replace("0x09", "(0x09)")
        txt = txt.replace(",", ", ")
        vis = min(t1, win[1]) - max(t0, win[0])
        if vis >= 1:
            axi.text((max(t0, win[0]) + min(t1, win[1])) / 2, 0.5,
                     txt.replace(", ", ",\n", 1) if vis < 2 else txt,
                     ha="center", va="center", fontsize=5.5 if vis >= 2 else 4.8)
    axes = []
    rows = [("ALE", "Канал A: ALE (вывод 30)", True)] + extra
    for i, (key, label, act_hi) in enumerate(rows):
        ax = fig.add_axes([0.10, top - (i + 1) * h + 0.02, 0.86, h - 0.03])
        xs, ys = wave(sig.get(key, []), total + 20, act_hi) if key != "PSEN" else ([0, total + 20], [5, 5])
        ax.plot(xs, ys, color="#1a7f37" if key == "ALE" else "#b3261e" if key == "RD" else "#6a1b9a" if key == "WR" else "#444", lw=1.1)
        ax.set_xlim(*win)
        ax.set_ylim(-2.5, 7.5)
        ax.set_yticks([0, 5])
        ax.set_xticks(range(int(win[0]), int(win[1]) + 1))
        ax.set_xticklabels([str(k - int(win[0])) for k in range(int(win[0]), int(win[1]) + 1)])
        ax.grid(True, color="#bbb", lw=0.4)
        ax.tick_params(labelsize=6, length=2)
        ax.text(0.995, 0.93, label, transform=ax.transAxes, ha="right", va="top", fontsize=6.5,
                bbox=dict(fc="white", ec="none", pad=1))
        ax.set_ylabel("U, В", fontsize=6)
        if i < n - 1:
            ax.set_xticklabels([])
        axes.append(ax)
    axes[-1].set_xlabel("t, мкс  (1 мкс/дел; ось Y: 5 В/дел)", fontsize=7)
    # отметки пропущенного ALE
    for t0, t1, op in ins:
        if op.startswith("MOVX") and win[0] <= t0 and t0 + 2 <= win[1]:
            axes[0].annotate("пропущен импульс ALE", xy=(t0 + 1.2, 0.3), xytext=(t0 + 1.3, -1.6),
                             ha="center", va="center", fontsize=5.5, color="#b3261e",
                             arrowprops=dict(arrowstyle="->", color="#b3261e", lw=0.6))
    fig.text(0.10, 0.012, f"{title}\nМодель по трассе выполнения (uCsim, 12 МГц); не снимок прибора Multisim. "
             f"t = 0 - {'начало итерации цикла проверки' if start == 0 else f'{start}-й машинный цикл от начала итерации цикла проверки'}.", fontsize=5.5, color="#333", va="bottom")
    out = os.path.join(HERE, "schematics", name)
    fig.savefig(out + ".png", dpi=250)
    fig.savefig(out + ".pdf")
    plt.close(fig)
    return sig, total


def main():
    res = json.load(open(os.path.join(HERE, "sim", "results.json"), encoding="utf-8"))
    sig1, t1 = draw("oscillogram_ale_ram", res["trace_ram"]["loop"], 4,
                    [("RD", "RD (P3.7, вывод 17), активный уровень 0", False),
                     ("WR", "WR (P3.6, вывод 16), активный уровень 0", False)],
                    "Задание 1: цикл теста ОЗУ")
    sig2, t2 = draw("oscillogram_ale_rom", res["trace_rom"]["loop"], 0,
                    [("RD", "RD (P3.7, вывод 17), активный уровень 0", False),
                     ("PSEN", "PSEN (вывод 29): не активен, код - в резидентном ПЗУ", False)],
                    "Задание 2: цикл подсчёта контрольной суммы ПЗУ")
    # цифры для отчёта
    stats = {}
    for k, (sig, total) in (("ram", (sig1, t1)), ("rom", (sig2, t2))):
        loop = res["trace_" + k]["loop"]
        stats[k] = {"loop_cycles": total, "ale_pulses_per_loop": len(sig["ALE"]),
                    "ale_expected_no_skip": int(total) * 2, "skipped": len([1 for x in loop if x["op"].startswith("MOVX")]), "rd": len(sig["RD"]), "wr": len(sig["WR"])}
    json.dump(stats, open(os.path.join(HERE, "sim", "scope_stats.json"), "w"), indent=1)
    print(stats)


if __name__ == "__main__":
    main()
