"""
Временные диаграммы SDA/SCL по журналу шины эмуляции (../sim/results.json) — аналог Logic Analyzer.
Запуск:  uv run --with matplotlib python plot_i2c.py
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(HERE, "..", "sim")
VDD = 3.3
BLUE, RED, GREY = "#1f4e9c", "#a01010", "#777777"


def transactions(events):
    out, cur = [], []
    for e in events:
        if e["kind"] == "S":
            cur = [e]
        else:
            cur.append(e)
            if e["kind"] == "P":
                out.append(cur)
    return out


def waveform(trs, gap_us=12.0):
    """-> (точки (t, scl, sda), аннотации). Время перенумеровано от 0 с паузами gap_us между транзакциями."""
    pts, notes = [], []
    shift = None
    st = {"t": 0.0, "scl": 1, "sda": 1}

    def put(t, scl=None, sda=None):
        t += shift
        scl = st["scl"] if scl is None else scl
        sda = st["sda"] if sda is None else sda
        pts.append((t, st["scl"], st["sda"]))
        pts.append((t, scl, sda))
        st.update(t=t, scl=scl, sda=sda)

    t_end_prev = 0.0
    for tr in trs:
        t0 = tr[0]["t"]
        shift = (t_end_prev + gap_us) - t0 if pts else gap_us - t0
        put(t0 - gap_us / 2, 1, 1)
        for e in tr:
            t, k = e["t"], e["kind"]
            if k == "S":
                put(t + 4, 1, 0)
                put(t + 8, 0, 0)
                notes.append(("mark", t + 5 + shift, "START"))
            elif k == "Sr":
                put(t + 0.5, 0, 1)
                put(t + 3, 1, 1)
                put(t + 6, 1, 0)
                put(t + 9, 0, 0)
                notes.append(("mark", t + 5 + shift, "повторный\nSTART"))
            elif k == "P":
                put(t + 0.5, 0, 0)
                put(t + 1.5, 1, 0)
                put(t + 3.5, 1, 1)
                notes.append(("mark", t + 2.5 + shift, "STOP"))
                t_end = t + 5
            else:
                v, b0 = e["value"], t
                for i in range(9):
                    bt = b0 + 10 * i
                    sda = ((v >> (7 - i)) & 1) if i < 8 else (0 if e["ack"] else 1)
                    put(bt + 0.5, 0, sda)
                    put(bt + 2.5, 1, sda)
                    put(bt + 7.5, 0, sda)
                if k == "addr":
                    lab = f"0x{v:02X}\nSLA+{'R' if e['read'] else 'W'}"
                else:
                    lab = f"0x{v:02X}\n" + ("данные (чтение)" if e["read"] else "данные")
                notes.append(("byte", b0 + 40 + shift, lab, b0 + 85 + shift, e["ack"], b0 + shift))
        t_end_prev = t_end + shift
        put(t_end + 5, 1, 1)
        t_end_prev = t_end + 5 + shift
    return pts, notes, t_end_prev


def draw_panel(ax, trs, title, byte_names=None):
    pts, notes, t_total = waveform(trs)
    xs = [p[0] for p in pts]
    scl = [p[1] * VDD * 0.75 + 5.0 for p in pts]
    sda = [p[2] * VDD * 0.75 + 0.0 for p in pts]
    ax.plot(xs, scl, color=BLUE, lw=0.9)
    ax.plot(xs, sda, color=RED, lw=0.9)
    ax.text(-4, 5.0 + VDD * 0.375, "SCL", color=BLUE, ha="right", va="center", fontsize=7)
    ax.text(-4, VDD * 0.375, "SDA", color=RED, ha="right", va="center", fontsize=7)
    names = iter(byte_names or [])
    for n in notes:
        if n[0] == "mark":
            ax.annotate(n[2], (n[1], VDD * 0.75 + 0.2), (n[1], 9.3), ha="center", va="bottom", fontsize=6,
                        arrowprops=dict(arrowstyle="-", color=GREY, lw=0.5))
        else:
            _, xm, lab, xa, ack, xb = n
            nm = next(names, None)
            ax.text(xm, 9.3, lab if nm is None else lab + "\n" + nm, ha="center", va="bottom", fontsize=6)
            ax.axvspan(xb, xb + 80, ymin=0.04, ymax=0.16, color="#e8eefb", lw=0)
            ax.text(xa + 2, -1.3, "ACK" if ack else "NACK", ha="center", va="top", fontsize=6,
                    color="#0a6a0a" if ack else RED, fontweight="bold")
    ax.set_xlim(-2, t_total + 4)
    ax.set_ylim(-3.2, 14.2)
    ax.set_title(title, fontsize=7.5, loc="left")
    ax.set_xlabel("t, мкс (отсчёт от начала фрагмента, шаг сетки 50 мкс = 5 тактов SCL)", fontsize=6)
    ax.set_yticks([])
    ax.tick_params(labelsize=6)
    ax.grid(axis="x", color="#cccccc", lw=0.3)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.set_xticks(range(0, int(t_total) + 50, 50))


def fig(trs_list, titles, fname, names=None, height=1.9):
    f, axs = plt.subplots(len(trs_list), 1, figsize=(6.3, height * len(trs_list) + 0.3))
    axs = [axs] if len(trs_list) == 1 else list(axs)
    for i, (ax, trs, ti) in enumerate(zip(axs, trs_list, titles)):
        draw_panel(ax, trs, ti, (names or [None] * 9)[i])
    f.tight_layout()
    f.savefig(os.path.join(SIM, fname), dpi=250)
    plt.close(f)


def main():
    res = json.load(open(os.path.join(SIM, "results.json"), encoding="utf-8"))
    n = next(r for r in res if r["name"] == "normal")
    trs = transactions(n["events"])
    polls = [t for t in trs if len(t) == 3 and t[1]["kind"] == "addr" and t[1]["value"] == 0xA0]
    write, nacks = trs[0], [t for t in polls if not t[1]["ack"]]
    ack_poll = next(t for t in trs[1:] if t[1]["kind"] == "addr" and t[1]["value"] == 0xA0 and t[1]["ack"]
                    and len(t) == 3)
    read = next(t for t in trs if any(e["kind"] == "Sr" for e in t) and t[1]["value"] == 0xA0)
    ds_w = next(t for t in trs if t[1]["kind"] == "addr" and t[1]["value"] == 0xD0 and len(t) == 7)
    ds_r = next(t for t in trs if t[1]["kind"] == "addr" and t[1]["value"] == 0xD0
                and any(e["kind"] == "Sr" for e in t))
    fig([[write, nacks[0]]],
        ["Запись байта 0x34 в ячейку 0x0000 24LC64; сразу после STOP — первый опрос (NACK: идёт цикл записи)"],
        "i2c_eeprom_write.png")
    fig([[nacks[-1], ack_poll]],
        ["ACK polling: последний опрос с NACK и первый с ACK — цикл записи завершён"],
        "i2c_ack_polling.png")
    fig([[read]],
        ["Случайное чтение ячейки 0x0000: адрес, повторный START, SLA+R, байт 0x34, NACK ведущего"],
        "i2c_eeprom_read.png")
    fig([[ds_w], [ds_r]],
        ["DS1307: запись времени — указатель 0x00, секунды 0x00 (CH=0), минуты 0x34, часы 0x12",
         "DS1307: чтение регистра секунд (адрес 0xD0 -> 0x00 -> repeated START -> 0xD1), получен 0x00"],
        "i2c_ds1307.png")
    print("диаграммы построены")


if __name__ == "__main__":
    main()
