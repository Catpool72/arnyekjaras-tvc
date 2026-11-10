#!/usr/bin/env python3
"""A keresés (design_search.py) eredményéből témánként a célhoz legközelebbi jelöltet
választja, a meglévőkkel együtt nehézség szerint sorba rendezi, és megírja a levels.py-t.

  python3 design_select.py <keresés.json>[:KULCS,KULCS...] ... [--write]
  (a kulcslista megadásakor abból a fájlból csak azok a témák jönnek; a meglévő pályák mindig)
"""
import json, sys
import design_search as DS

HU = {s[0]: s[2] for s in DS.SPECS}
HU.update(DELIKAPU="Déli kapu", PIACTER="Piactér", VARUDVAR="Várudvar")
DESC = {
    "KERTVAROS": "Alacsony házak, sok kert és fa, két őr: a legbarátságosabb negyed.",
    "HALPIAC": "Reggeli piac a folyóparti negyedben, három őrrel.",
    "TEMETOKERT": "Fák és sírkertek között, egyetlen felhővel.",
    "CEHHAZAK": "Sűrűn épített mesterutcák, sok sarokkal és szűk közzel.",
    "RAKPART": "Nyitott rakodóterek és kevés takarás.",
    "MALOMSOR": "Négy őr a malmok és raktárak között.",
    "SIKATOROK": "Szűk sikátorok délelőtt: rövidek az árnyékok, de sok a takarás.",
    "VAMHAZ": "A vámház körül négy őr és egyetlen felhő; késő délutánig kell kivárni.",
    "FOTER": "Nagy, nyitott tér délelőtt: kevés az árnyék, sok a figyelő szem.",
    "KOLOSTOR": "Az utolsó: öregtorony és kerengő, öt őr. Hibátlan játékkal is csak percekkel a kapuzárás előtt lehet kijutni.",
    "VAROSHAZA": "Délben indulsz a városháza terén, öt őrrel.",
    "KASZARNYA": "Délután egykor, öt őr és egyetlen felhő: kevés az idő.",
    "KINCSTAR": "Hat őr délben, nyitott udvarokkal.",
}
FIELDS = ["key", "name", "hu", "time", "desc", "start", "gate", "blds", "trees", "pkg", "clouds", "guards"]


TARGET = {s[0]: s[7] for s in DS.SPECS}


def pick(res):
    by = {}
    for r in res:
        if r["seed"] is not None:
            r["target"] = TARGET[r["key"]]
        by.setdefault(r["key"], []).append(r)
    # témánként egy jelölt úgy, hogy a sorba rendezett nehézségek a lehető legegyenletesebben
    # emelkedjenek: a szomszédos különbségek négyzetösszege legyen minimális (helyi keresés)
    keys = list(by)
    pick_i = {k: min(range(len(by[k])), key=lambda j: abs(by[k][j]["metrics"]["diff"] - (by[k][j]["target"] or 0)))
              for k in keys}

    def cost(p):
        d = sorted(by[k][p[k]]["metrics"]["diff"] for k in keys)
        gaps = [b - a for a, b in zip(d, d[1:])]
        mean = (d[-1] - d[0]) / len(gaps)
        return sum((g - mean) ** 2 for g in gaps) - 4 * (d[-1] - d[0])   # egyenletes és széles skála

    improved = True
    while improved:
        improved = False
        for k in keys:
            for j in range(len(by[k])):
                trial = dict(pick_i, **{k: j})
                if cost(trial) < cost(pick_i) - 1e-9:
                    pick_i, improved = trial, True
    chosen = [by[k][pick_i[k]] for k in keys]
    chosen.sort(key=lambda r: r["metrics"]["diff"])
    return chosen


def fmt_level(L):
    def t(v):
        return repr(tuple(v)) if isinstance(v, (list, tuple)) and len(v) == 2 and all(
            isinstance(a, int) for a in v) else repr(v)
    out = [f'    dict(key={L["key"]!r}, name={L["name"]!r}, hu={L["hu"]!r}, time={L["time"]!r},',
           f'         desc={L["desc"]!r},',
           f'         start={t(L["start"])}, gate={t(L["gate"])},',
           f'         blds={[list(b) for b in L["blds"]]!r},',
           f'         trees={[list(x) for x in L["trees"]]!r},',
           f'         pkg={[tuple(p) for p in L["pkg"]]!r},',
           f'         clouds={[dict(rx=c["rx"], ry=c["ry"], y=c["y"], x=float(c["x"])) for c in L["clouds"]]!r},',
           f'         guards={[(bool(lp), [tuple(p) for p in pts]) for lp, pts in L["guards"]]!r}),']
    return "\n".join(out)


def write(chosen):
    src = open("levels.py", encoding="utf-8").read()
    head = src[:src.index("LEVELS = [")]
    body = []
    for r in chosen:
        L = dict(r["level"])
        L["hu"] = L.get("hu") or HU[L["key"]]
        L["desc"] = L.get("desc") or DESC.get(L["key"], "")
        if L["key"] in DESC and not r["level"].get("desc"):
            L["desc"] = DESC[L["key"]]
        body.append(fmt_level(L))
    open("levels.py", "w", encoding="utf-8").write(head + "LEVELS = [\n" + "\n\n".join(body) + "\n]\n")


if __name__ == "__main__":
    res, seen_existing = [], set()
    for arg in [a for a in sys.argv[1:] if not a.startswith("--")]:
        path, _, keys = arg.partition(":")
        for r in json.load(open(path)):
            if r["seed"] is None:
                if r["key"] in seen_existing:
                    continue
                seen_existing.add(r["key"])
            elif keys and r["key"] not in keys.split(","):
                continue
            res.append(r)
    chosen = pick(res)
    for n, r in enumerate(chosen, 1):
        m = r["metrics"]
        print(f"{n:2d}. {HU[r['key']]:12} nehézség {m['diff']:5.1f}  tűrés {m['tol']:2d}  figyelt {m['watch']:4.1f}%  "
              f"őr {m['guards']}  indul {m['time']:>5}  kijut {m['finish']}  (seed {r['seed']})")
    if "--write" in sys.argv:
        write(chosen)
        print("levels.py megírva")
