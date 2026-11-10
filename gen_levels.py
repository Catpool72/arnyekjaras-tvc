#!/usr/bin/env python3
"""Pályajelölt-generátor: utcahálós város a megadott stílusban.

Egy jelölt egy levels.py-formátumú dict. A tervezés menete (design_search.py):
stílus + indulás + őrök + felhők -> sok seed -> megoldóval mért nehézség -> a célhoz legjobb.
"""
import random
from collections import deque

W, H = 32, 20
SHAPES = [(3, 2), (3.5, 2), (3.5, 2.2), (4, 2.5)]

# stílus: tömbszélesség, tömbmagasság, utcaszélesség-esélyek, tömbtípus-arányok, emeletek
STYLES = {
    "kert":    dict(bw=(4, 6), bh=(3, 4), wide=0.3, mix=dict(haz=0.45, kert=0.45, ter=0.10), floors=(1, 2)),
    "varos":   dict(bw=(3, 5), bh=(2, 4), wide=0.2, mix=dict(haz=0.70, kert=0.15, ter=0.15), floors=(1, 3)),
    "sikator": dict(bw=(2, 4), bh=(2, 3), wide=0.0, mix=dict(haz=0.88, kert=0.06, ter=0.06), floors=(2, 3)),
    "ter":     dict(bw=(3, 6), bh=(2, 4), wide=0.4, mix=dict(haz=0.45, kert=0.10, ter=0.45), floors=(2, 4)),
    "var":     dict(bw=(3, 5), bh=(3, 4), wide=0.3, mix=dict(haz=0.55, kert=0.10, ter=0.35), floors=(2, 3)),
}


def cuts(R, lo, hi, size, wide):
    """Utcavonalak egy tengelyen: a [lo, hi] belső tartomány tömbökre bontva.
    Vissza: tömbök (a, b) listája; köztük 1 (vagy 2) széles utca."""
    blocks, a = [], lo
    while True:
        w = R.randint(*size)
        b = a + w - 1
        if b > hi - 2:
            b = hi
            if b - a + 1 >= 2:
                blocks.append((a, b))
            elif blocks:
                blocks[-1] = (blocks[-1][0], b)
            break
        blocks.append((a, b))
        a = b + 1 + (2 if R.random() < wide else 1)
        if a > hi - 1:
            break
    return blocks


def bfs(walk, s):
    seen = {s}
    dq = deque([s])
    while dq:
        x, y = dq.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (x + dx, y + dy)
            if n in walk and n not in seen:
                seen.add(n)
                dq.append(n)
    return seen


def generate(seed, style, guards, clouds, time, key, name, hu="", desc="", focus=0.0):
    """focus: 0..1 – mekkora eséllyel választ az őr olyan járőrutat, amely a csomagok vagy a
    kapu közelében halad (nagyobb = nehezebb)."""
    R = random.Random(f"{key}:{seed}")
    S = STYLES[style]
    blds, trees = [], []
    solid = set()
    xs = cuts(R, 2, 29, S["bw"], S["wide"])
    ys = cuts(R, 2, 17, S["bh"], S["wide"])
    kinds = list(S["mix"])
    weights = [S["mix"][k] for k in kinds]
    keep = None
    if style == "var":   # középen nagy öregtorony
        cx, cy = len(xs) // 2, len(ys) // 2
        keep = (cx, cy)
    for j, (y0, y1) in enumerate(ys):
        for i, (x0, x1) in enumerate(xs):
            w, h = x1 - x0 + 1, y1 - y0 + 1
            kind = "torony" if keep == (i, j) else R.choices(kinds, weights)[0]
            if kind == "torony":
                blds.append([x0, y0, w, h, 4])
            elif kind == "haz":
                # a tömb 1-3 házra osztva a hosszabb oldal mentén, néha udvarral
                horiz = w >= h
                L = w if horiz else h
                parts, p = [], 0
                while p < L:
                    q = min(L, p + R.randint(1, max(1, L // 2 + 1)))
                    parts.append((p, q))
                    p = q
                for (p, q) in parts:
                    if R.random() < 0.15 and len(parts) > 1:
                        continue          # udvar
                    fl = R.randint(*S["floors"])
                    if R.random() < 0.06:
                        fl = 4            # torony
                    if horiz:
                        blds.append([x0 + p, y0, q - p, h, fl])
                    else:
                        blds.append([x0, y0 + p, w, q - p, fl])
            elif kind == "kert":
                for _ in range(max(1, (w * h) // 4)):
                    tx, ty = R.randint(x0, x1), R.randint(y0, y1)
                    if [tx, ty] not in trees:
                        trees.append([tx, ty])
                if R.random() < 0.4 and w * h >= 6:
                    blds.append([x0, y0, 1, 1, 1])   # fészer
            else:  # tér: üres, néha egy fa vagy kút (1x1 alacsony)
                if R.random() < 0.5:
                    trees.append([R.randint(x0, x1), R.randint(y0, y1)])
    for b in blds:
        for yy in range(b[1], b[1] + b[3]):
            for xx in range(b[0], b[0] + b[2]):
                solid.add((xx, yy))
    trees = [t for t in trees if tuple(t) not in solid]
    solid |= {tuple(t) for t in trees}
    walk = {(x, y) for y in range(1, H - 1) for x in range(1, W - 1) if (x, y) not in solid}

    # kezdőhely egy sarokban, kapu a túlsó oldalon
    corners = [(1, 1), (30, 1), (1, 18), (30, 18)]
    start = R.choice(corners)
    sides = []
    if start[1] == 1:
        sides.append("bottom")
    else:
        sides.append("top")
    sides.append("right" if start[0] == 1 else "left")
    side = R.choice(sides)
    if side in ("top", "bottom"):
        gx = R.randint(8, 23) if True else 0
        gx = gx if abs(gx - start[0]) > 6 else 31 - gx
        gate = (gx, 0 if side == "top" else 19)
    else:
        gy = R.randint(4, 15)
        gate = (0 if side == "left" else 31, gy)
    reach = bfs(walk, start)
    inner = (min(max(gate[0], 1), 30), min(max(gate[1], 1), 18))
    if inner not in reach:
        return None

    # csomagok: egymástól és a kezdőhelytől távol
    pool = [p for p in reach if abs(p[0] - start[0]) + abs(p[1] - start[1]) > 8 and p != inner]
    if len(pool) < 10:
        return None
    best = None
    for _ in range(200):
        pk = R.sample(pool, 3)
        d = min(abs(a[0] - b[0]) + abs(a[1] - b[1]) for i, a in enumerate(pk) for b in pk[i + 1:])
        if best is None or d > best[0]:
            best = (d, pk)
    pkg = sorted(best[1])
    targets = pkg + [inner]

    # őrök: utcaszakaszok és tömb körüli körök
    def seg_ok(p, q):
        x, y = p
        while True:
            if (x, y) not in walk:
                return False
            if (x, y) == q:
                return True
            x += (q[0] > x) - (q[0] < x)
            y += (q[1] > y) - (q[1] < y)

    cands = []
    for (x0, x1) in xs:                       # körök tömbök körül
        for (y0, y1) in ys:
            a, b = (x0 - 1, y0 - 1), (x1 + 1, y1 + 1)
            loop = [a, (b[0], a[1]), b, (a[0], b[1])]
            if all(seg_ok(p, q) for p, q in zip(loop, loop[1:] + loop[:1])):
                cands.append((True, loop))
    for y in range(1, 19):                    # vízszintes szakaszok
        x = 1
        while x < 31:
            if (x, y) in walk:
                x2 = x
                while (x2 + 1, y) in walk:
                    x2 += 1
                if x2 - x >= 5:
                    a = R.randint(x, max(x, x2 - 6))
                    b = min(x2, a + R.randint(5, 12))
                    cands.append((False, [(a, y), (b, y)]))
                x = x2 + 1
            else:
                x += 1
    for x in range(1, 31):                    # függőleges szakaszok
        y = 1
        while y < 19:
            if (x, y) in walk:
                y2 = y
                while (x, y2 + 1) in walk:
                    y2 += 1
                if y2 - y >= 4:
                    a = R.randint(y, max(y, y2 - 5))
                    b = min(y2, a + R.randint(4, 10))
                    cands.append((False, [(x, a), (x, b)]))
                y = y2 + 1
            else:
                y += 1
    def path_cells(loop, pts):
        cells = set()
        seq = pts + ([pts[0]] if loop else [])
        for p, q in zip(seq, seq[1:]):
            x, y = p
            while True:
                cells.add((x, y))
                if (x, y) == q:
                    break
                x += (q[0] > x) - (q[0] < x)
                y += (q[1] > y) - (q[1] < y)
        return cells

    R.shuffle(cands)
    near = sorted(cands, key=lambda c: min(abs(a[0] - t[0]) + abs(a[1] - t[1])
                                             for a in path_cells(*c) for t in targets) + R.random() * 3)
    gs = []
    used = set()
    pool_rand, pool_near = list(cands), list(near)
    while len(gs) < guards and (pool_rand or pool_near):
        src = pool_near if (R.random() < focus and pool_near) or not pool_rand else pool_rand
        loop, pts = src.pop(0)
        cells = path_cells(loop, pts)
        if any(abs(c[0] - start[0]) + abs(c[1] - start[1]) < 6 for c in cells):
            continue
        if any(p in cells for p in pkg):
            continue
        if any(abs(c[0] - inner[0]) + abs(c[1] - inner[1]) < 2 for c in cells):
            continue
        if len(cells & used) > 2:
            continue
        used |= cells
        gs.append((loop, pts))
    if len(gs) < guards:
        return None

    cl = []
    for _ in range(clouds):
        rx, ry = R.choice(SHAPES)
        cl.append(dict(rx=rx, ry=ry, y=R.randint(2, 17), x=float(R.randint(-6, 24))))
    if len(blds) > 60 or len(trees) > 30:
        return None
    return dict(key=key, name=name, hu=hu, desc=desc, time=time, start=start, gate=gate,
                blds=blds, trees=trees, pkg=pkg, clouds=cl, guards=gs, seed=seed, style=style)
