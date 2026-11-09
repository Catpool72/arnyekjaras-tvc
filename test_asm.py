#!/usr/bin/env python3
"""A tényleges shadow.asm és vision.asm futtatása a z80sim-ben, összevetve
a böngészős demó számításaival. Ciklusszámot is mér."""
import math, os, random
import gen_tables as G
from test_shadow import js_shadow, parse_inc
from z80sim import Z80Sim

HERE = os.path.dirname(os.path.abspath(__file__))
W, H = G.W, G.H


def js_vision(hgt, sh, guards):
    """A demó computeVision()-jének átirata. sh: 32x20, hgt: magasságtérkép (0 = járható)."""
    blk = lambda x, y: x < 0 or y < 0 or x >= W or y >= H or hgt[y][x] != 0

    def los(x0, y0, x1, y1):
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        e, x, y = dx + dy, x0, y0
        while not (x == x1 and y == y1):
            e2 = 2 * e
            if e2 >= dy:
                e += dy; x += sx
            if e2 <= dx:
                e += dx; y += sy
            if x == x1 and y == y1:
                break
            if blk(x, y):
                return False
        return True

    vis = [[0] * W for _ in range(H)]
    for gx, gy in guards:
        for dy in range(-5, 6):
            for dx in range(-5, 6):
                if dx * dx + dy * dy > 30:
                    continue
                x, y = gx + dx, gy + dy
                if x < 0 or y < 0 or x >= W or y >= H or hgt[y][x] != 0 or sh[y][x]:
                    continue
                if los(gx, gy, x, y):
                    vis[y][x] = 1
    return vis


def region(sim, base):
    a = lambda x, y: base + (y + G.MY) * G.STRIDE + (x + G.MX)
    return [[sim.mem[a(x, y)] for x in range(W)] for y in range(H)]


def main():
    sim = Z80Sim([os.path.join(HERE, f) for f in
                  ("mem_test.inc", "shadow.asm", "vision.asm", "suntab.inc", "vistab.inc", "level1.inc", "level2.inc")],
                 mem_fill=0xAA)
    SHBUF = sim.sym["SHBUF"]
    rnd = random.Random(72)
    bad = cases = 0
    worst_shadow = 0
    vg_cycles = []
    for i, L in enumerate(G.LEVELS):
        hgt = G.height_map(L)
        p = L["name"]
        sim.call("TerrainBuild", hl=sim.sym[f"{p}_CLASS"])
        walk = [(x, y) for y in range(H) for x in range(W) if not hgt[y][x]]
        for q in range(G.Q_COUNT):
            minute = G.Q_FIRST + q * 10
            for cx in ((-8.0, 15.7, 36.0) if q % 6 == 0 else (rnd.uniform(-8, 37),)):
                clouds = [dict(c, x=cx + 5 * n) for n, c in enumerate(L["clouds"])]
                # --- árnyék
                c0 = sim.cycles
                sim.call("ShadowClear")
                for n, c in enumerate(clouds):
                    sim.call("StampCloud", hl=sim.sym[f"{p}_CLOUD{n}"],
                             d=math.floor(c["x"]) & 0xFF, e=math.floor(c["y"]))
                sim.call("ShadowCast", a=q, hl=sim.sym[f"{p}_CLASS"])
                worst_shadow = max(worst_shadow, sim.cycles - c0)
                got = region(sim, SHBUF)
                ref = js_shadow(hgt, minute, clouds)
                cases += 1
                ok = all(got[y][x] == ref[y][x] for y in range(H) for x in range(W) if not hgt[y][x])
                if not ok:
                    bad += 1
                    print(f"ÁRNYÉK ELTÉR: {p} q={q} felhő={cx:.1f}")
                    continue
                # --- látómező: 3 véletlen őrhely, ebből az árnyékállapotból
                guards = rnd.sample(walk, 3)
                if q % 2:   # előző látómező visszaállítása is teszteljen
                    for gx, gy in rnd.sample(walk, 2):
                        sim.call("VisionGuard", b=gx, c=gy)
                sim.call("VisionClear")
                for gx, gy in guards:
                    c1 = sim.cycles
                    sim.call("VisionGuard", b=gx, c=gy)
                    vg_cycles.append(sim.cycles - c1)
                vref = js_vision(hgt, ref, guards)
                cases += 1
                full = region(sim, SHBUF)
                exp = [[3 if vref[y][x] else ref[y][x] if not hgt[y][x] else full[y][x] for x in range(W)] for y in range(H)]
                if full != exp:
                    bad += 1
                    print(f"LÁTÓMEZŐ ELTÉR: {p} q={q} őrök={guards}")
                    continue
                # --- IsShadow / IsSeen
                for x, y in rnd.sample(walk, 5):
                    sim.call("IsShadow", b=x, c=y)
                    s_ok = sim.r["a"] == exp[y][x] and sim.f["z"] == (exp[y][x] == 0)
                    sim.call("IsSeen", b=x, c=y)
                    v_ok = sim.f["z"] == bool(vref[y][x])
                    cases += 1
                    if not (s_ok and v_ok):
                        bad += 1
                        print(f"LEKÉRDEZÉS ELTÉR: {p} q={q} ({x},{y})")
    print(f"{cases} eset, {bad} eltérés")
    if bad:
        return False
    print(f"Árnyék (törlés + felhők + vetés) legrosszabb: {worst_shadow} ciklus = {worst_shadow / 3125:.1f} ms")
    print(f"VisionGuard őrönként: átlag {sum(vg_cycles) // len(vg_cycles)}, max {max(vg_cycles)} ciklus")
    return bad == 0


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
