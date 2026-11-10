#!/usr/bin/env python3
"""A böngészős demó (arnyekjaras.html) pályáinak frissítése a levels.py-ból.

  python3 gen_demo.py <demo.html>
"""
import json, re, sys
import levels as LV


def js_levels():
    out = []
    for i, L in enumerate(LV.LEVELS):
        h, m = map(int, L["time"].split(":"))
        hu = L.get("hu") or L["name"].title()
        out.append(dict(
            name=hu, min=h * 60 + m, start=list(L["start"]), gate=list(L["gate"]),
            intro=[f"{i + 1}. pálya: {hu}", f"Indulás {L['time']}-kor. {L.get('desc', '')}".strip()],
            blds=L["blds"], trees=L["trees"], pkg=[list(p) for p in L["pkg"]],
            paths=[dict(p=[list(p) for p in pts], loop=lp) for lp, pts in L["guards"]],
            clouds=[dict(x=c["x"], y=c["y"], rx=c["rx"], ry=c["ry"]) for c in L["clouds"]]))
    return "const LEVELS=" + json.dumps(out, ensure_ascii=False, separators=(",", ":")) + ";"


def patch(path):
    s = open(path, encoding="utf-8").read()
    a = s.index("const LEVELS=[")
    b = s.index("\n];", a) + 3
    s = s[:a] + js_levels() + s[b:]
    # utolsó pálya utáni szöveg a pályaszámmal
    s = re.sub(r"'(Mindhárom|Mind a \d+) pályán kijutottál, a [^']*'\+fmt\(S\.min\)\+'-kor\.'",
               f"'Mind a {len(LV.LEVELS)} pályán kijutottál, az utolsóról '+fmt(S.min)+'-kor.'", s)
    open(path, "w", encoding="utf-8").write(s)


if __name__ == "__main__":
    patch(sys.argv[1])
