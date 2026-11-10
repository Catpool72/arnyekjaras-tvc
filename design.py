#!/usr/bin/env python3
"""Pályatervező segéd: ellenőrzés, ASCII-térkép és nehézségi mérőszámok.

  python3 design.py              # minden pálya: táblázat
  python3 design.py 5 -m         # az 5. pálya térképe és részletes adatai

Mérőszámok:
  leggyorsabb  a leggyorsabb kijutás ideje (játékperc) és a szükséges várakozások száma
  tűrés        a leglassabb lépéstempó (5, 8, 12 vagy 20 képkocka/lépés), amellyel még kijutható;
               a játék ismétlési tempója 5, tehát 5 = csak hibátlan játékkal, 20 = negyed tempóval is
  figyelt      a nap során átlagosan a járható mezők hány %-át látja őr (vagy van őr mellett)
  nehézség     összesített pontszám (lásd difficulty())
"""
import sys
from concurrent.futures import ProcessPoolExecutor
import levels as LV
import gen_tables as G
import solver as S

W, H = G.W, G.H
TOL_STEPS = [5, 8, 12, 20]


def validate(i):
    """Szerkezeti hibák listája (üres = rendben)."""
    L = LV.LEVELS[i]
    lv = S.Level(i)
    err = []
    gx, gy = L["gate"]
    if not (gx in (0, W - 1) or gy in (0, H - 1)) or (gx, gy) in ((0, 0), (0, H - 1), (W - 1, 0), (W - 1, H - 1)):
        err.append("a kapu nem a fal közepén van")
    inner = (min(max(gx, 1), W - 2), min(max(gy, 1), H - 2))
    if not lv.walk(*inner):
        err.append(f"a kapu előtti mező {inner} nem járható")
    for what, p in [("kezdőhely", L["start"])] + [("csomag", p) for p in L["pkg"]]:
        if not lv.walk(*p):
            err.append(f"{what} {p} nem járható")
    if len(L["pkg"]) != 3:
        err.append("pontosan 3 csomag kell")
    if len(L["guards"]) > 6 or len(L["clouds"]) > 3:
        err.append("legfeljebb 6 őr és 3 felhő lehet")
    if len(L["name"]) > 18:
        err.append("túl hosszú név")
    for b in L["blds"]:
        if b[4] not in (1, 2, 3, 4) or b[0] < 1 or b[1] < 1 or b[0] + b[2] > W - 1 or b[1] + b[3] > H - 1:
            err.append(f"hibás épület {b}")
    for n, (loop, pts) in enumerate(L["guards"]):
        seq = pts + ([pts[0]] if loop else [])
        for a, b in zip(seq, seq[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                err.append(f"{n + 1}. őr: ferde szakasz {a}->{b}")
                continue
            x, y = a
            while True:
                if not lv.walk(x, y):
                    err.append(f"{n + 1}. őr útja nem járható mezőn halad: {(x, y)}")
                    break
                if (x, y) == tuple(b):
                    break
                x += (b[0] > x) - (b[0] < x)
                y += (b[1] > y) - (b[1] < y)
    for u in range(0, S.MOVE + 1):
        if lv.unsafe(*L["start"], u):
            err.append("a kezdőhely az indításkor veszélyes")
            break
    return err


def watched(i, lv=None):
    lv = lv or S.Level(i)
    walk = [(x, y) for y in range(H) for x in range(W) if lv.walk(x, y)]
    tot = n = 0
    for u in range(0, lv.u_end, S.FR_MINUTE * 10):
        bad = lv.danger(*lv.state(u))[0]
        tot += sum(1 for p in walk if p in bad) / len(walk)
        n += 1
    return 100 * tot / n


def tolerance(i, lv):
    best = None
    for m in TOL_STEPS:
        if S.solve(i, move=m, lv=lv)["ok"]:
            best = m
        else:
            break
    return best


def difficulty(m):
    """Összesített nehézség, kb. 0–100. Főleg a tűrés (mennyire kell pontosan játszani),
    utána a figyelt terület és az őrök száma, végül a szükséges várakozás aránya."""
    if not m["ok"]:
        return 999
    tol = {5: 25, 8: 16, 12: 8, 20: 0}[m["tol"]]
    wait_share = min(1, m["fast_min"] / m["day_min"])
    return round(tol + 0.9 * m["watch"] + 2 * m["guards"] + 15 * wait_share, 1)


def use_levels(levels):
    """Futás közben más pályalistával dolgozik (jelöltek mérése)."""
    LV.LEVELS[:] = levels
    G.reload_levels()
    import gen_game
    gen_game.reload_levels()


def measure(i):
    lv = S.Level(i)
    r = S.solve(i, lv=lv)
    m = dict(i=i, name=LV.LEVELS[i]["name"], guards=len(LV.LEVELS[i]["guards"]),
             clouds=len(LV.LEVELS[i]["clouds"]), time=LV.LEVELS[i]["time"], ok=r["ok"],
             day_min=lv.minutes, err=validate(i))
    if r["ok"]:
        p = r["path"]
        m["fast_min"] = r["u"] // S.FR_MINUTE
        m["finish"] = S.fmt(lv, r["u"])
        m["waits"] = sum(1 for a, b in zip(p, p[1:]) if a[1:3] == b[1:3])
        m["tol"] = tolerance(i, lv)
    m["watch"] = watched(i, lv)
    m["diff"] = difficulty(m)
    return m


def ascii_map(i, u=0):
    L = LV.LEVELS[i]
    lv = S.Level(i)
    bad, sh = lv.danger(*lv.state(u))
    grid = [[" "] * W for _ in range(H)]
    for y in range(H):
        for x in range(W):
            h = lv.hgt[y][x]
            if x in (0, W - 1) or y in (0, H - 1):
                grid[y][x] = "#"
            elif h == 1.4:
                grid[y][x] = "T"
            elif h:
                grid[y][x] = str(int(h))
            elif (x, y) in bad:
                grid[y][x] = "x"
            elif sh[y][x]:
                grid[y][x] = "."
            else:
                grid[y][x] = " "
    for loop, pts in L["guards"]:
        for p in pts:
            grid[p[1]][p[0]] = "o"
    for p in L["pkg"]:
        grid[p[1]][p[0]] = "P"
    grid[L["start"][1]][L["start"][0]] = "S"
    grid[L["gate"][1]][L["gate"][0]] = "G"
    print(f"{i + 1}. {L['name']}  ({S.fmt(lv, u)})   # fal, 1-4 épület, T fa, . árnyék, x figyelt, o őrpont")
    print("   " + "".join(str(x % 10) for x in range(W)))
    for y in range(H):
        print(f"{y:2d} " + "".join(grid[y]))


def table(ms):
    print(f"{'#':>2} {'pálya':18} {'ind.':>5} {'őr':>2} {'f.':>2} {'kijut':>6} {'perc':>4} {'vár':>4} "
          f"{'tűrés':>5} {'figy%':>5} {'nehézség':>8}")
    for m in ms:
        if m["ok"]:
            print(f"{m['i'] + 1:2d} {m['name']:18} {m['time']:>5} {m['guards']:2d} {m['clouds']:2d} {m['finish']:>6} "
                  f"{m['fast_min']:4d} {m['waits']:4d} {m['tol']:5d} {m['watch']:5.1f} {m['diff']:8.1f}"
                  + ("  HIBA: " + "; ".join(m["err"]) if m["err"] else ""))
        else:
            print(f"{m['i'] + 1:2d} {m['name']:18} {m['time']:>5} {m['guards']:2d} {m['clouds']:2d}  NINCS MEGOLDÁS"
                  f"  figy {m['watch']:.1f}%" + ("  HIBA: " + "; ".join(m["err"]) if m["err"] else ""))


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    idx = [int(a) - 1 for a in args] or list(range(len(LV.LEVELS)))
    if "-m" in sys.argv:
        for i in idx:
            ascii_map(i)
            print()
    with ProcessPoolExecutor(2) as ex:
        ms = list(ex.map(measure, idx))
    table(ms)
