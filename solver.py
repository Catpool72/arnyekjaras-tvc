#!/usr/bin/env python3
"""Pálya-megoldó: van-e győztes út, és milyen gyors.

A játék időzítését követi (arnyek.asm): 1 egység = 1 képkocka normál sebességgel.
  - játékperc 12 egységenként, őrlépés 22 egységenként
  - lépés: 5 egység (nyomva tartott irány ismétlése), várakozás: 8 egység (szóköz, 1 képkocka)
  - lépéskor a játék az új mezőt azonnal, még az időléptetés előtt is ellenőrzi
  - a felhők 8.8 fixpontosan, percenként +13, a játékkal azonos visszatekeréssel
  - árnyék és látómező a demóval azonos képlettel (ezt a test_game a TVC-n is ellenőrzi)
Lebukás: napos, őr által látott mező, vagy őr 1 mezőn belül.
"""
import sys
from functools import lru_cache
import gen_tables as G
import gen_game as GG
from test_shadow import js_shadow
from test_asm import js_vision

FR_MINUTE, FR_GUARD, MOVE, WAIT = 12, 22, 5, 8
W, H = G.W, G.H


class Level:
    def __init__(self, idx):
        self.L = G.LEVELS[idx]
        self.E = GG.EXTRA[self.L["name"]]
        self.hgt = G.height_map(self.L)
        self.minutes = (G.Q_COUNT - self.E["q0"]) * 10
        self.u_end = self.minutes * FR_MINUTE
        # felhők percenként (egész x)
        cl = [dict(x=int(round(x * 256)), rx=-int(-c["rx"] // 1), y=c["y"], c=c)
              for c, x in zip(self.L["clouds"], self.E["cloud_x"])]
        self.cloud_at = []
        for m in range(self.minutes + 1):
            self.cloud_at.append(tuple(c["x"] >> 8 for c in cl))
            for c in cl:
                old = c["x"] >> 8
                c["x"] += 13
                hi = c["x"] >> 8
                if hi != old and hi - c["rx"] >= 34:
                    c["x"] = (-(c["rx"] + 2)) << 8
        self.cdefs = [c["c"] for c in cl]
        # őrök lépésenként
        gs = [dict(p=p, loop=lp, x=p[0][0], y=p[0][1], i=1, d=1) for lp, p in self.E["paths"]]
        self.guards_at = []
        for _ in range(self.u_end // FR_GUARD + 2):
            self.guards_at.append(tuple((g["x"], g["y"]) for g in gs))
            for g in gs:
                tx, ty = g["p"][g["i"]]
                if (g["x"], g["y"]) == (tx, ty):
                    if g["loop"]:
                        g["i"] = (g["i"] + 1) % len(g["p"])
                    else:
                        g["i"] += g["d"]
                        if not 0 <= g["i"] < len(g["p"]):
                            g["d"] = -g["d"]
                            g["i"] += 2 * g["d"]
                    tx, ty = g["p"][g["i"]]
                if g["x"] != tx:
                    g["x"] += 1 if tx > g["x"] else -1
                elif g["y"] != ty:
                    g["y"] += 1 if ty > g["y"] else -1

    @lru_cache(maxsize=None)
    def shadow(self, q, cxs):
        clouds = [dict(c, x=float(x)) for c, x in zip(self.cdefs, cxs)]
        return js_shadow(self.hgt, G.Q_FIRST + min(q, G.Q_COUNT - 1) * 10, clouds)

    @lru_cache(maxsize=None)
    def danger(self, q, cxs, gstep):
        sh = self.shadow(q, cxs)
        guards = self.guards_at[gstep]
        vis = js_vision(self.hgt, sh, guards)
        bad = set((x, y) for y in range(H) for x in range(W) if vis[y][x])
        for gx, gy in guards:
            bad |= {(gx, gy), (gx + 1, gy), (gx - 1, gy), (gx, gy + 1), (gx, gy - 1)}
        return frozenset(bad), sh

    def state(self, u):
        m = u // FR_MINUTE
        q = self.E["q0"] + m // 10
        return q, self.cloud_at[min(m, self.minutes)], u // FR_GUARD

    def unsafe(self, x, y, u):
        q, cxs, gs = self.state(u)
        return (x, y) in self.danger(q, cxs, gs)[0]

    def walk(self, x, y):
        return 0 <= x < W and 0 <= y < H and not self.hgt[y][x]


def solve(idx, verbose=True):
    lv = Level(idx)
    pk = {p: i for i, p in enumerate(lv.E["pkg"])}
    full = (1 << len(pk)) - 1
    gate = tuple(lv.L["gate"])
    sx, sy = lv.E["start"]
    buckets = {0: {(sx, sy, 0): None}}
    prev = {}
    u = 0
    while u <= lv.u_end:
        cur = buckets.pop(u, None)
        if cur:
            for st, par in cur.items():
                prev[(u,) + st] = par
            for (x, y, mask) in cur:
                if (x, y) == gate:
                    path, k = [], (u, x, y, mask)
                    while k:
                        path.append(k)
                        k = prev[k]
                    path.reverse()
                    return dict(level=idx, ok=True, u=u, path=path, lv=lv)
                # várakozás
                nu = u + WAIT
                if nu <= lv.u_end and not lv.unsafe(x, y, nu):
                    buckets.setdefault(nu, {}).setdefault((x, y, mask), (u, x, y, mask))
                # lépés
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = x + dx, y + dy
                    if not lv.walk(nx, ny):
                        continue
                    if (nx, ny) == gate and mask != full:
                        continue
                    nu = u + MOVE
                    if nu > lv.u_end or any(lv.unsafe(nx, ny, t) for t in range(u, nu + 1)):
                        continue
                    nm = mask | (1 << pk[(nx, ny)]) if (nx, ny) in pk else mask
                    buckets.setdefault(nu, {}).setdefault((nx, ny, nm), (u, x, y, mask))
        u += 1
    return dict(level=idx, ok=False, lv=lv)


def fmt(lv, u):
    m = lv.E["q0"] * 10 + u // FR_MINUTE + G.Q_FIRST
    return f"{m // 60}:{m % 60:02d}"


def report(r):
    lv = r["lv"]
    name = lv.E["title"]
    if not r["ok"]:
        print(f"{name}: NINCS MEGOLDÁS kapuzárásig")
        return
    path = r["path"]
    moves = sum(1 for a, b in zip(path, path[1:]) if a[1:3] != b[1:3])
    waits = len(path) - 1 - moves
    print(f"{name}: megoldható, leggyorsabb kijutás {fmt(lv, r['u'])}-kor "
          f"({fmt(lv, 0)}-tól), {moves} lépés, {waits} várakozás (x8)")


if __name__ == "__main__":
    idx = [int(a) - 1 for a in sys.argv[1:]] or range(len(G.LEVELS))
    for i in idx:
        report(solve(i))
