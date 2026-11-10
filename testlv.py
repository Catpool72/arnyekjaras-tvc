"""Pályafüggetlen segédek a tvcsim-es tesztekhez: a koordinátákat a pályaadatokból
számolják, így a tesztek a pályák cseréje vagy átrendezése után is érvényesek."""
import gen_tables as G
import levels as LV

W, H = G.W, G.H
KEY = {(1, 0): 0x20, (-1, 0): 0x40, (0, -1): 0x02, (0, 1): 0x04}   # jobb, bal, fel, le (8. sor)


def walkable(i, x, y):
    hgt = G.height_map(G.LEVELS[i])
    return 0 < x < W - 1 and 0 < y < H - 1 and not hgt[y][x]


def approach(i, target, avoid=()):
    """Egy járható szomszéd és a billentyű, amellyel onnan a célra lép: ((x, y), bit)."""
    tx, ty = target
    for (dx, dy), bit in KEY.items():
        fx, fy = tx - dx, ty - dy
        if walkable(i, fx, fy) and (fx, fy) not in avoid:
            return (fx, fy), bit
    raise ValueError(f"nincs járható szomszéd: {target}")


def gate_approach(i):
    """A kapu előtti mező és a kapu felé mutató billentyű."""
    gx, gy = LV.LEVELS[i]["gate"]
    inner = (min(max(gx, 1), W - 2), min(max(gy, 1), H - 2))
    d = (gx - inner[0], gy - inner[1])
    return inner, KEY[d]


def safe_run(i, frames=300):
    """A kezdőhelyről egyenesen, falig/épületig: olyan irány, ahol minden mező biztonságos
    az első `frames` képkockában. Vissza: (billentyű, a várt megállóhely, lépések száma)."""
    import solver as S
    lv = S.Level(i)
    sx, sy = LV.LEVELS[i]["start"]
    best = None
    for (dx, dy), bit in KEY.items():
        x, y, cells = sx, sy, []
        while walkable(i, x + dx, y + dy):
            x, y = x + dx, y + dy
            cells.append((x, y))
        if len(cells) < 2:
            continue
        if any(lv.unsafe(cx, cy, u) for cx, cy in cells for u in range(0, frames, 4)):
            continue
        if best is None or len(cells) < len(best[2]):
            best = (bit, cells[-1], cells)
    return best


def safe_package(i, frames=800):
    """Egy csomag és egy szomszédja, amelyek az indulás utáni `frames` képkockában biztonságosak:
    ((honnan x, y), billentyű, csomag)."""
    import solver as S
    lv = S.Level(i)
    pkgs = [tuple(p) for p in LV.LEVELS[i]["pkg"]]
    for p in pkgs:
        tx, ty = p
        for (dx, dy), bit in KEY.items():
            f = (tx - dx, ty - dy)
            if not walkable(i, *f) or f in pkgs:
                continue
            if any(lv.unsafe(*c, u) for c in (f, p) for u in range(0, frames, 4)):
                continue
            return f, bit, p
    raise ValueError("nincs biztonságos csomag")


TITLE_SHIFT = 60     # ennyi képkocka/kör kell a címképről a pályabevezetőig


def skip_title(script):
    """A játék a címképpel indul: szóköz a 2. és 20. képkocka (kör) között, majd minden
    eseményt TITLE_SHIFT-tel később futtat. Így a tesztek forgatókönyvei a címkép előtti
    időzítéssel írhatók; a kiolvasott adatok kulcsából a hívó vonja le az eltolást."""
    out = ["key 2 7 32", "key 20 7 0"]
    for line in script:
        p = line.split()
        if p and p[0] in ("key", "poke", "dump", "shot"):
            p[1] = str(int(p[1]) + TITLE_SHIFT)
        out.append(" ".join(p))
    return out
