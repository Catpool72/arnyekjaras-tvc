#!/usr/bin/env python3
"""Összeveti a Z80-as algoritmust (a generált .inc táblákból, bájtszinten emulálva)
a böngészős demó lebegőpontos árnyékszámításával, mindkét pályán, minden 10 perces
napállásra és többféle felhőhelyzetre."""
import math, re, os
import gen_tables as G

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = G.W, G.H


def parse_inc(name):
    """Címke -> bájtlista (db és dw kicsi-endian), ahogy egy assembler is fordítaná."""
    labels, cur = {}, None
    for line in open(os.path.join(HERE, name)):
        line = line.split(";")[0].rstrip()
        if not line:
            continue
        m = re.match(r"^(\w+):", line)
        if m:
            cur = labels.setdefault(m.group(1), [])
            continue
        op, args = line.split(None, 1)
        for v in (int(a) for a in args.split(",")):
            if op == "db":
                cur.append(v & 0xFF)
            else:
                cur += [v & 0xFF, (v >> 8) & 0xFF]
    return labels


def js_shadow(hgt, minute, clouds):
    """A demó computeShadow() függvényének szó szerinti átirata."""
    sh = [[0] * W for _ in range(H)]
    q = math.floor(minute / 10) * 10
    sx, sy, k = G.sun(q)
    for c in clouds:
        cx, cy, rx, ry = math.floor(c["x"]), math.floor(c["y"]), math.ceil(c["rx"]), math.ceil(c["ry"])
        for dy in range(-ry, ry + 1):
            for dx in range(-rx, rx + 1):
                if (dx * dx) / (c["rx"] ** 2) + (dy * dy) / (c["ry"] ** 2) > 1:
                    continue
                x, y = cx + dx, cy + dy
                if 0 <= x < W and 0 <= y < H:
                    sh[y][x] = 2
    for y in range(H):
        for x in range(W):
            hh = hgt[y][x]
            if not hh:
                continue
            ln = min(9, hh * k)
            d = 0.35
            while d <= ln:
                cx, cy = math.floor(x + .5 + sx * d), math.floor(y + .5 + sy * d)
                if 0 <= cx < W and 0 <= cy < H:
                    sh[cy][cx] = 1
                d += 0.35
    return sh


def z80_shadow(suntab, cls, masks, minute, clouds):
    """A shadow.asm lépéseinek bájtszintű utánzása 16 bites címaritmetikával."""
    BASE = 0x8000
    buf = bytearray(G.STRIDE * G.ROWS)
    addr = lambda x, y: BASE + (y + G.MY) * G.STRIDE + (x + G.MX)
    # StampCloud
    for c, m in zip(clouds, masks):
        w, h, ox, oy = m[0], m[1], m[2], m[3]
        dst = addr(math.floor(c["x"]) - ox, math.floor(c["y"]) - oy)
        p = 4
        for r in range(h):
            for i in range(w):
                if m[p]:
                    buf[dst + i - BASE] = m[p]
                p += 1
            dst += G.STRIDE
    # ShadowCompute
    q = (math.floor(minute / 10) * 10 - G.Q_FIRST) // 10
    e = q * G.ENTRY
    counts = suntab[e:e + 6]
    offs = suntab[e + 6:e + G.ENTRY]
    for y in range(H):
        for x in range(W):
            c = cls[y * W + x]
            if not c:
                continue
            n = counts[c - 1]
            hl = addr(x, y)
            for j in range(n):
                o = offs[2 * j] | (offs[2 * j + 1] << 8)
                buf[((hl + o) & 0xFFFF) - BASE] = 1
    return [[buf[addr(x, y) - BASE] for x in range(W)] for y in range(H)]


def main():
    suntab = parse_inc("suntab.inc")["SUNTAB"]
    assert len(suntab) == G.Q_COUNT * G.ENTRY
    total = bad = 0
    for i, L in enumerate(G.LEVELS):
        lab = parse_inc(f"level{i + 1}.inc")
        cls = lab[f"{L['name']}_CLASS"]
        masks = [lab[f"{L['name']}_CLOUD{n}"] for n in range(len(L["clouds"]))]
        hgt = G.height_map(L)
        for q in range(G.Q_COUNT):
            minute = G.Q_FIRST + q * 10
            for cx in (-8.0, 0.4, 6.0, 15.7, 27.2, 36.0):   # felhők a pálya szélein túl is
                clouds = [dict(c, x=cx + 5 * n) for n, c in enumerate(L["clouds"])]
                a = js_shadow(hgt, minute, clouds)
                b = z80_shadow(suntab, cls, masks, minute, clouds)
                # csak a járható cellák számítanak (fal/épület/fa cellájára nem lehet lépni)
                a = [[a[y][x] if not hgt[y][x] else 0 for x in range(W)] for y in range(H)]
                b = [[b[y][x] if not hgt[y][x] else 0 for x in range(W)] for y in range(H)]
                total += 1
                if a != b:
                    bad += 1
                    if bad <= 3:
                        diff = [(x, y, a[y][x], b[y][x]) for y in range(H) for x in range(W) if a[y][x] != b[y][x]]
                        print(f"ELTÉRÉS {L['name']} {minute // 60}:{minute % 60:02d} felhő x={cx}: {diff[:6]}")
    print(f"{total} eset, {bad} eltérés")
    return bad == 0


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
