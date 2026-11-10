#!/usr/bin/env python3
"""Pályák keresése: témánként sok seed, megoldóval mérve; az eredmény JSON-ba kerül.

  python3 design_search.py <kimenet.json> [seedek száma pályánként]
"""
import json, sys
from concurrent.futures import ProcessPoolExecutor
import gen_levels as GL

# key, név (TVC), magyar név, stílus, indulás, őrök, felhők, célnehézség
SPECS = [
    ("KERTVAROS",  "KERTVAROS",   "Kertváros",   "kert",    "7:00", 2, 2, 15, 0.0),
    ("HALPIAC",    "HALPIAC",     "Halpiac",     "varos",   "7:00", 3, 2, 22, 0.2),
    ("TEMETOKERT", "TEMETOKERT",  "Temetőkert",  "kert",    "8:00", 3, 1, 28, 0.3),
    ("CEHHAZAK",   "CEHHAZAK",    "Céhházak",    "sikator", "8:00", 3, 2, 33, 0.3),
    ("RAKPART",    "RAKPART",     "Rakpart",     "ter",     "7:00", 3, 1, 38, 0.4),
    ("MALOMSOR",   "MALOMSOR",    "Malomsor",    "varos",   "9:00", 4, 2, 41, 0.5),
    ("SIKATOROK",  "SIKATOROK",   "Sikátorok",   "sikator", "10:00", 4, 1, 49, 0.5),
    ("VAMHAZ",     "VAMHAZ",      "Vámház",      "varos",   "9:00", 4, 1, 53, 0.6),
    ("FOTER",      "FOTER",       "Főtér",       "ter",     "10:00", 4, 2, 57, 0.6),
    ("KOLOSTOR",   "KOLOSTOR",    "Kolostor",    "var",     "11:00", 5, 2, 61, 0.7),
    ("VAROSHAZA",  "VAROSHAZA",   "Városháza",   "ter",     "12:00", 5, 2, 65, 0.8),
    ("KASZARNYA",  "KASZARNYA",   "Kaszárnya",   "varos",   "13:00", 5, 1, 69, 0.8),
    ("KINCSTAR",   "KINCSTAR",    "Kincstár",    "ter",     "12:00", 6, 1, 75, 0.9),
]


def evaluate(job):
    key, seed = job
    spec = next(s for s in SPECS if s[0] == key)
    k, name, hu, style, time, guards, clouds, target, focus = spec
    cand = GL.generate(seed, style, guards, clouds, time, k, name, hu, focus=focus)
    if cand is None:
        return None
    import design as D
    D.use_levels([cand])
    err = D.validate(0)
    if err:
        return None
    m = D.measure(0)
    if not m["ok"]:
        return None
    m.pop("err", None)
    return dict(key=key, seed=seed, target=target, metrics=m, level=cand)


def existing():
    import levels as LV
    import design as D
    out = []
    for i, L in enumerate(list(LV.LEVELS)):
        out.append(dict(key=L["key"], seed=None, target=None, metrics=D.measure(i), level=L))
    return out


if __name__ == "__main__":
    out_path = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 8
    res = existing()
    jobs = [(s[0], seed) for s in SPECS for seed in range(1, n + 1)]
    with ProcessPoolExecutor(2) as ex:
        for r in ex.map(evaluate, jobs, chunksize=1):
            if r:
                res.append(r)
                m = r["metrics"]
                print(f"{r['key']:11} seed {r['seed']:3d}: nehézség {m['diff']:5.1f} (cél {r['target']}), "
                      f"tűrés {m['tol']}, figyelt {m['watch']:.1f}%, kijut {m['finish']}", flush=True)
                json.dump(res, open(out_path, "w"), default=list)
    json.dump(res, open(out_path, "w"), default=list)
    print("KÉSZ")


def adaptive(key, max_seeds=12, band=4.0):
    """Egy téma: seedek sorban, amíg egy jelölt a cél ±band sávjába esik."""
    found = []
    for seed in range(1, max_seeds + 1):
        r = evaluate((key, seed))
        if r:
            found.append(r)
            m = r["metrics"]
            print(f"{key:11} seed {seed:3d}: nehézség {m['diff']:5.1f} (cél {r['target']}), tűrés {m['tol']}, "
                  f"figyelt {m['watch']:.1f}%, kijut {m['finish']}", flush=True)
            if abs(m["diff"] - r["target"]) <= band:
                break
    return found
