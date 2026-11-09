#!/usr/bin/env python3
"""Árnyékjárás – árnyéktáblák generátora a Z80-as rutinhoz.

Kimenet: suntab.inc (napállás-táblák), level1.inc, level2.inc (osztálytérkép + felhőmaszkok).

Puffer-elrendezés (shadow.asm-mel egyezően):
  SHBUF: 64 bájt széles, 38 sor; a 32x20-as játéktér a (16, 9) pozícióban kezdődik.
  A margó (9 cella minden irányban) miatt az árnyékvetés és a felhők vágás nélkül írhatnak.
"""
import math, os, sys

W, H = 32, 20
STRIDE, MX, MY, ROWS = 64, 16, 9, 38
Q_FIRST, Q_COUNT = 6 * 60, 72          # 6:00-tól 10 percenként, 72 kvantum (18:00-ig)
MAXLEN = 9

# magasság -> osztály (0 = nem vet árnyékot)
HEIGHT_CLASS = {1: 1, 1.4: 2, 2: 3, 3: 4, 4: 5}
CLASS_HEIGHT = {c: h for h, c in HEIGHT_CLASS.items()}
NCLASS = 5
MAXOFF = 13                            # bejegyzés: 8 bájt fej + 13*2 = 34 -> 64 bájtra kerekítjük? lásd ENTRY
ENTRY = 32                             # 6 bájt darabszám + 13 offset * 2 = 32


def sun(minute):
    """Pontosan a demó (JS) képlete."""
    h = minute / 60
    az = (90 + (h - 6) * 15) * math.pi / 180
    el = max(6, 62 * math.sin(math.pi * (h - 6) / 12)) * math.pi / 180
    return -math.sin(az), math.cos(az), 1 / math.tan(el)


def path_for(minute):
    """Egyedi cellaoffsetek a vetés irányában, első elérés sorrendjében, + első elérés távolsága."""
    sx, sy, _ = sun(minute)
    seen, out = set(), []
    d = 0.35
    while d <= MAXLEN:
        cx, cy = math.floor(0.5 + sx * d), math.floor(0.5 + sy * d)
        if (cx, cy) != (0, 0) and (cx, cy) not in seen:
            seen.add((cx, cy))
            out.append((cx, cy, d))
        d += 0.35
    return out


def entry_for(q):
    minute = Q_FIRST + q * 10
    _, _, k = sun(minute)
    path = path_for(minute)
    counts = []
    for c in range(1, NCLASS + 1):
        ln = min(MAXLEN, CLASS_HEIGHT[c] * k)
        counts.append(sum(1 for (_, _, d) in path if d <= ln))
    n = max(counts)
    assert n <= MAXOFF, (q, n)
    offs = [(dx, dy) for (dx, dy, _) in path[:n]]
    return counts, offs


def gen_suntab():
    lines = ["; Generálta: gen_tables.py  –  ne szerkeszd kézzel",
             f"; {Q_COUNT} bejegyzés, mindegyik {ENTRY} bájt: 6 bájt darabszám (osztály 1..5 + 0),",
             f"; utána {MAXOFF} db 16 bites előjeles offset (dy*{STRIDE}+dx) a SHBUF-ban.",
             "SUNTAB:"]
    for q in range(Q_COUNT):
        counts, offs = entry_for(q)
        m = Q_FIRST + q * 10
        words = [dy * STRIDE + dx for dx, dy in offs] + [0] * (MAXOFF - len(offs))
        lines.append(f"; {m // 60}:{m % 60:02d}")
        lines.append("        db " + ",".join(str(c) for c in counts) + ",0")
        lines.append("        dw " + ",".join(str(w & 0xFFFF) for w in words))
    return "\n".join(lines) + "\n"


# ---- pályák (a demóval azonos adatok)
LEVELS = [
    dict(name="DELIKAPU", gate=(28, 19),
         blds=[[3,3,3,2,1],[10,1,2,2,2],[21,1,3,3,3],[14,3,4,2,2],[11,5,1,4,3],[4,6,2,2,2],[18,6,2,2,1],
               [24,7,4,2,2],[7,10,3,2,3],[26,10,1,2,1],[19,11,2,2,2],[12,12,3,2,1],[25,13,3,3,3],[5,14,2,2,2],
               [17,15,4,2,3],[9,17,2,2,2],[3,17,1,1,1]],
         trees=[[5,1],[9,4],[29,5],[2,9],[23,9],[15,10],[3,13],[12,15],[25,17],[27,2]],
         clouds=[dict(rx=3.5, ry=2.2, y=9)]),
    dict(name="PIACTER", gate=(16, 0),
         blds=[[3,2,4,4,4],[24,2,5,3,2],[10,3,2,1,1],[19,3,2,1,1],
               [12,8,1,1,1],[15,8,1,1,1],[18,8,1,1,1],[12,11,1,1,1],[15,11,1,1,1],[18,11,1,1,1],
               [2,9,3,3,2],[26,9,3,4,3],[7,14,3,2,2],[21,14,4,2,2],[14,16,3,2,3],[28,16,2,2,1]],
         trees=[[9,7],[22,7],[6,12],[24,12],[11,15],[20,17],[2,15],[29,6]],
         clouds=[dict(rx=4, ry=2.5, y=5), dict(rx=3, ry=2, y=15)]),
    dict(name="VARUDVAR", gate=(31, 10),
         blds=[[13,7,6,6,4],[3,2,2,2,4],[26,2,2,2,4],[3,16,2,2,4],[26,16,2,2,4],
               [8,2,4,2,2],[19,16,5,2,2],[7,15,4,2,1],[22,5,1,1,1],[9,10,1,1,1],[23,9,1,4,3]],
         trees=[[11,5],[20,5],[11,14],[21,13],[6,10],[28,9],[16,3],[16,16]],
         clouds=[dict(rx=3.5, ry=2, y=4), dict(rx=4, ry=2.5, y=11), dict(rx=3, ry=2, y=17)]),
]


def height_map(L):
    hgt = [[0] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            if x in (0, W - 1) or y in (0, H - 1):
                hgt[y][x] = 2
    for b in L["blds"]:
        for y in range(b[1], b[1] + b[3]):
            for x in range(b[0], b[0] + b[2]):
                hgt[y][x] = b[4]
    for x, y in L["trees"]:
        hgt[y][x] = 1.4
    gx, gy = L["gate"]
    hgt[gy][gx] = 0
    return hgt


def cloud_mask(c):
    """Pontosan a demó feltétele; a középpont a maszk (rx,ry) cellája."""
    rx, ry = math.ceil(c["rx"]), math.ceil(c["ry"])
    rows = []
    for dy in range(-ry, ry + 1):
        rows.append([2 if (dx * dx) / (c["rx"] ** 2) + (dy * dy) / (c["ry"] ** 2) <= 1 else 0
                     for dx in range(-rx, rx + 1)])
    return rx, ry, rows


def gen_level(i, L):
    hgt = height_map(L)
    p = L["name"]
    out = [f"; Generálta: gen_tables.py – {i + 1}. pálya", f"{p}_CLASS:  ; {W}x{H} bájt, árnyékosztály 0..5"]
    for row in hgt:
        out.append("        db " + ",".join(str(HEIGHT_CLASS.get(h, 0)) for h in row))
    for n, c in enumerate(L["clouds"]):
        rx, ry, rows = cloud_mask(c)
        out.append(f"{p}_CLOUD{n}:  ; szélesség, magasság, bal-felső eltolás (-rx,-ry), majd a maszk")
        out.append(f"        db {2 * rx + 1},{2 * ry + 1},{rx},{ry}")
        for r in rows:
            out.append("        db " + ",".join(map(str, r)))
    return "\n".join(out) + "\n"


# ---- őrök látómezeje
VIS_R2 = 30          # dx*dx+dy*dy <= 30, mint a demóban


def bresenham_mid(dx1, dy1):
    """A demó los() függvényének köztes cellái (0,0)-tól (dx1,dy1)-ig, a végpontok nélkül."""
    dx, dy = abs(dx1), -abs(dy1)
    sx, sy = (1 if 0 < dx1 else -1), (1 if 0 < dy1 else -1)
    e, x, y, out = dx + dy, 0, 0, []
    while not (x == dx1 and y == dy1):
        e2 = 2 * e
        if e2 >= dy:
            e += dy; x += sx
        if e2 <= dx:
            e += dx; y += sy
        if x == dx1 and y == dy1:
            break
        out.append((x, y))
    return out


def vis_targets():
    return [(dx, dy, bresenham_mid(dx, dy)) for dy in range(-5, 6) for dx in range(-5, 6)
            if dx * dx + dy * dy <= VIS_R2]


def gen_vistab():
    t = vis_targets()
    lines = ["; Generálta: gen_tables.py  –  ne szerkeszd kézzel",
             "; db N, majd célonként: dw cél-offset, db köztes cellák száma, dw köztes offsetek",
             "VISTAB:", f"        db {len(t)}"]
    for dx, dy, mid in t:
        o = lambda x, y: (y * STRIDE + x) & 0xFFFF
        lines.append(f"        dw {o(dx, dy)}")
        lines.append(f"        db {len(mid)}" + (("\n        dw " + ",".join(str(o(x, y)) for x, y in mid)) if mid else ""))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "vistab.inc"), "w").write(gen_vistab())
    here = os.path.dirname(os.path.abspath(__file__))
    open(os.path.join(here, "suntab.inc"), "w").write(gen_suntab())
    for i, L in enumerate(LEVELS):
        open(os.path.join(here, f"level{i + 1}.inc"), "w").write(gen_level(i, L))
    mx = max(max(entry_for(q)[0]) for q in range(Q_COUNT))
    print(f"suntab.inc: {Q_COUNT}*{ENTRY} = {Q_COUNT * ENTRY} bájt, leghosszabb offsetlista: {mx}")
