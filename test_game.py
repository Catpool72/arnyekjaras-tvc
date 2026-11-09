#!/usr/bin/env python3
"""A lefordított arnyek.cas tesztje a tvcsim-ben.

1. Árnyék + látómező: várakozás közben (szóköz nyomva) több időpontban kiolvassa a
   SHBUF-ot, az órát, a felhőket és az őrök helyét, és összeveti a demó számításával.
2. Mozgás: jobbra lépés, megáll a fánál.
3. Lebukás: a játékos egy látott mezőre kerül.
4. Kapuzárás: 17:59 után.
5. Győzelem: minden csomag felvéve, lépés a kapura, majd a 2. pálya indul.
"""
import os, re, subprocess, sys
import gen_tables as G
from test_shadow import js_shadow
from test_asm import js_vision


def solver_level(i):
    import solver
    return solver.Level(i)

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.join(HERE, "harness", "tvcsim")
CAS = os.path.join(HERE, "arnyek.cas")
SYM = {m.group(1): int(m.group(2), 16) for m in
       re.finditer(r"^(\w+):\s+EQU\s+0x([0-9A-Fa-f]+)", open(os.path.join(HERE, "arnyek.sym")).read(), re.M)}
W, H = G.W, G.H

ROW_SPACE, BIT_SPACE = 7, 0x20
ROW_CUR, BIT_RIGHT, BIT_DOWN = 8, 0x20, 0x04


def run(script, frames, iters=False):
    path = os.path.join(HERE, "_t.txt")
    open(path, "w").write("\n".join(script) + "\n")
    env = dict(os.environ, HOOK=str(SYM["vsync"]))
    if iters:
        env["ITER"] = "1"
    out = subprocess.run([SIM, CAS, path, str(frames + 30)], capture_output=True, text=True, cwd=HERE, env=env)
    os.remove(path)
    if out.returncode != 0:
        raise SystemExit(f"tvcsim hiba: {out.stderr}")
    dumps = {}
    for line in out.stdout.splitlines():
        m = re.match(r"dump f(\d+) ([0-9A-F]{4}): (.*)", line)
        if m:
            data = bytes.fromhex(m.group(3).replace(" ", ""))
            dumps[(int(m.group(1)), int(m.group(2), 16))] = data
    return dumps


def dump_state(f):
    """Parancsok a játékállapot és a SHBUF kiolvasásához az f. képkockán."""
    s = [f"dump {f} {SYM['level']} {SYM['BSS_LEN'] if 'BSS_LEN' in SYM else 80}"]
    for y in range(H):
        s.append(f"dump {f} {SYM['SHBUF'] + (y + G.MY) * G.STRIDE + G.MX} {W}")
    return s


def state_at(d, f):
    bss = d[(f, SYM["level"])]
    v = lambda name, n=1: bss[SYM[name] - SYM["level"]: SYM[name] - SYM["level"] + n]
    sh = [list(d[(f, SYM["SHBUF"] + (y + G.MY) * G.STRIDE + G.MX)]) for y in range(H)]
    clouds = []
    for i in range(v("ncloud")[0]):
        c = v("clouds", 18)[i * 6:(i + 1) * 6]
        xi = c[4] - 256 if c[4] > 127 else c[4]
        clouds.append(dict(x=xi + c[3] / 256, y=c[2]))
    guards = []
    for i in range(v("nguard")[0]):
        g = v("guards", 32)[i * 8:(i + 1) * 8]
        guards.append((g[0], g[1]))
    return dict(level=v("level")[0], state=v("state")[0], q=v("q")[0], mm=v("mm")[0],
                px=v("px")[0], py=v("py")[0], clouds=clouds, guards=guards, sh=sh,
                allgot=v("allgot")[0])


def check_world(st):
    L = G.LEVELS[st["level"]]
    hgt = G.height_map(L)
    clouds = [dict(c, x=s["x"]) for c, s in zip(L["clouds"], st["clouds"])]
    for c, s in zip(clouds, st["clouds"]):
        c["y"] = s["y"]
    minute = G.Q_FIRST + st["q"] * 10
    ref = js_shadow(hgt, minute, clouds)
    vis = js_vision(hgt, ref, st["guards"])
    bad = [(x, y, st["sh"][y][x], 3 if vis[y][x] else ref[y][x])
           for y in range(H) for x in range(W)
           if not hgt[y][x] and st["sh"][y][x] != (3 if vis[y][x] else ref[y][x])]
    return bad


def main():
    fails = 0

    # --- 1. árnyék és látómező várakozás közben
    script = [f"key 30 {ROW_SPACE} {BIT_SPACE}", f"key 32 {ROW_SPACE} 0",      # indítás
              f"key 40 {ROW_SPACE} {BIT_SPACE}"]                                 # várakozás (nyomva)
    frames = list(range(45, 1400, 45))
    for f in frames:
        script += dump_state(f)
    d = run(script, frames[-1] + 2)
    seen_qs, last = set(), None
    lv1 = solver_level(0)
    for f in frames:
        st = state_at(d, f)
        bad = check_world(st)
        bss = d[(f, SYM["level"])]
        u = ((st["q"] - lv1.E["q0"]) * 10 + st["mm"]) * 12 + bss[SYM["sub"] - SYM["level"]]
        if st["state"] == 0 and list(st["guards"]) != list(lv1.guards_at[u // 22]):
            bad = bad or [("őrök", st["guards"], lv1.guards_at[u // 22])]
        seen_qs.add(st["q"])
        last = st
        if bad:
            fails += 1
            print(f"ELTÉRÉS f{f} q={st['q']} őrök={st['guards']}: {bad[:5]}")
    print(f"1. árnyék/látómező: {len(frames)} kiolvasás, {len(seen_qs)} napállás, "
          f"utolsó állapot={last['state']} q={last['q']}  -> {'OK' if not fails else 'HIBA'}")

    # --- 2. mozgás: (1,1)-ről jobbra, a fa (5,1)-nél megáll
    script = [f"key 30 {ROW_SPACE} {BIT_SPACE}", f"key 32 {ROW_SPACE} 0",
              f"key 40 {ROW_CUR} {BIT_RIGHT}", f"key 90 {ROW_CUR} 0"] + dump_state(95)
    st = state_at(run(script, 97), 95)
    ok = (st["px"], st["py"]) == (4, 1)
    fails += not ok
    print(f"2. mozgás: játékos itt: ({st['px']},{st['py']}), várt (4,1) -> {'OK' if ok else 'HIBA'}")

    # --- 3. lebukás: egy látott mezőre tesszük a játékost
    st0 = state_at(run([f"key 30 {ROW_SPACE} {BIT_SPACE}", f"key 32 {ROW_SPACE} 0"] + dump_state(40), 42), 40)
    seen = [(x, y) for y in range(H) for x in range(W) if st0["sh"][y][x] == 3
            and all(abs(x - gx) + abs(y - gy) > 1 for gx, gy in st0["guards"])]
    x, y = seen[0]
    # a mellette lévő szabad mezőről lépünk rá
    hgt = G.height_map(G.LEVELS[0])
    nx = next((x + dx, y + dy, key) for dx, dy, key in ((-1, 0, BIT_RIGHT), (0, -1, BIT_DOWN))
              if not hgt[y + dy][x + dx])
    script = [f"key 30 {ROW_SPACE} {BIT_SPACE}", f"key 32 {ROW_SPACE} 0",
              f"poke 41 {SYM['px']} {nx[0]}", f"poke 41 {SYM['py']} {nx[1]}",
              f"poke 41 {SYM['gacc']} 0",
              f"key 42 {ROW_CUR} {nx[2]}", f"key 46 {ROW_CUR} 0", "shot 50 lose.ppm"] + dump_state(48)
    st = state_at(run(script, 52), 48)
    ok = st["state"] == 2 and (st["px"], st["py"]) == (x, y)
    fails += not ok
    print(f"3. lebukás a ({x},{y}) látott mezőn: állapot={st['state']} -> {'OK' if ok else 'HIBA'}")

    # --- 4. kapuzárás
    script = [f"key 30 {ROW_SPACE} {BIT_SPACE}", f"key 32 {ROW_SPACE} 0",
              f"poke 40 {SYM['q']} 71", f"poke 40 {SYM['mm']} 9", f"poke 40 {SYM['sub']} 0"] + dump_state(60)
    st = state_at(run(script, 62), 60)
    ok = st["state"] == 2 and st["q"] == 72
    fails += not ok
    print(f"4. kapuzárás: állapot={st['state']} q={st['q']} -> {'OK' if ok else 'HIBA'}")

    # --- 5. győzelem: csomagok felvéve, a kapu fölé tesszük, lefelé lép
    pk = SYM["pkgs"]
    script = [f"key 30 {ROW_SPACE} {BIT_SPACE}", f"key 32 {ROW_SPACE} 0",
              f"poke 40 {pk + 2} 1", f"poke 40 {pk + 5} 1", f"poke 40 {pk + 8} 1",
              f"poke 40 {SYM['allgot']} 1", f"poke 40 {SYM['got_n']} 3",
              f"poke 40 {SYM['px']} 28", f"poke 40 {SYM['py']} 18", f"poke 40 {SYM['gacc']} 0",
              f"poke 40 {SYM['need_redraw']} 1",
              f"key 42 {ROW_CUR} {BIT_DOWN}", f"key 46 {ROW_CUR} 0", "shot 50 win.ppm"] + dump_state(48) + \
             [f"key 60 {ROW_SPACE} {BIT_SPACE}", f"key 62 {ROW_SPACE} 0", "shot 90 level2.ppm"] + dump_state(90)
    d = run(script, 92)
    st, st2 = state_at(d, 48), state_at(d, 90)
    ok = st["state"] == 1 and st2["level"] == 1 and st2["state"] == 3
    fails += not ok
    print(f"5. győzelem: állapot={st['state']}, utána pálya={st2['level'] + 1} állapot={st2['state']} -> {'OK' if ok else 'HIBA'}")
    bad = check_world(st2)
    fails += bool(bad)
    print(f"   2. pálya kezdőképe árnyék/látómező: {'OK' if not bad else bad[:5]}")

    # --- 6. a 2. pálya után a 3., annak megnyerése után játék vége, majd új játék
    #     (a kezdő rajzolás kb. 30 képkocka, ezért 40-től)
    script = [f"poke 40 {SYM['level']} 1", f"poke 40 {SYM['state']} 1",
              f"key 42 {ROW_SPACE} {BIT_SPACE}", f"key 46 {ROW_SPACE} 0", "shot 90 level3.ppm"] + dump_state(90) + \
             [f"key 100 {ROW_SPACE} {BIT_SPACE}", f"key 102 {ROW_SPACE} 0",
              f"poke 110 {pk + 2} 1", f"poke 110 {pk + 5} 1", f"poke 110 {pk + 8} 1",
              f"poke 110 {SYM['allgot']} 1", f"poke 110 {SYM['got_n']} 3",
              f"poke 110 {SYM['px']} 30", f"poke 110 {SYM['py']} 10", f"poke 110 {SYM['gacc']} 0",
              f"key 112 {ROW_CUR} {BIT_RIGHT}", f"key 116 {ROW_CUR} 0", "shot 125 done.ppm"] + dump_state(125) + \
             [f"key 140 {ROW_SPACE} {BIT_SPACE}", f"key 144 {ROW_SPACE} 0"] + dump_state(150) + \
             [f"key 160 {ROW_SPACE} {BIT_SPACE}", f"key 164 {ROW_SPACE} 0"] + dump_state(210)
    d = run(script, 212)
    s3, sw, so, s1 = state_at(d, 90), state_at(d, 125), state_at(d, 150), state_at(d, 210)
    ok = s3["level"] == 2 and not check_world(s3) and sw["state"] == 1 and so["state"] == 4 and \
         s1["level"] == 0 and s1["state"] == 3
    fails += not ok
    print(f"6. 3. pálya kezdőképe {'OK' if not check_world(s3) else 'HIBA'}, megnyerése: állapot={sw['state']}, "
          f"szóközre játék vége ({so['state']}), újabb szóközre pálya={s1['level'] + 1} állapot={s1['state']} "
          f"-> {'OK' if ok else 'HIBA'}")

    # --- 7. a pályakezdéskor felépített térképek (CLASSBUF, BASEBUF) mindhárom pályán
    import gen_game as GG
    for i, L in enumerate(G.LEVELS):
        sc = []
        if i:
            sc = [f"poke 40 {SYM['level']} {i - 1}", f"poke 40 {SYM['state']} 1",
                  f"key 42 {ROW_SPACE} {BIT_SPACE}", f"key 46 {ROW_SPACE} 0"]
        f = 90
        sc += [f"dump {f} {SYM['level']} 1"] + [f"dump {f} {SYM['CLASSBUF'] + y * 32} 32" for y in range(H)] + \
              [f"dump {f} {SYM['BASEBUF'] + y * 32} 32" for y in range(H)]
        d = run(sc, f + 2)
        cls = [b for y in range(H) for b in d[(f, SYM['CLASSBUF'] + y * 32)]]
        base = [b for y in range(H) for b in d[(f, SYM['BASEBUF'] + y * 32)]]
        hgt = G.height_map(L)
        want_cls = [G.HEIGHT_CLASS.get(hgt[y][x], 0) for y in range(H) for x in range(W)]
        ok = d[(f, SYM['level'])][0] == i and cls == want_cls and base == GG.base_map(L)
        fails += not ok
        print(f"7. {i + 1}. pálya felépített térképei: {'OK' if ok else 'HIBA'}")

    # --- 8. életek: háromszori kapuzárás -> játék vége, rekord; szóközre új játék
    def timeout(f):
        return [f"poke {f} {SYM['q']} 71", f"poke {f} {SYM['mm']} 9", f"poke {f} {SYM['sub']} 11"]
    def space(f):
        return [f"key {f} {ROW_SPACE} {BIT_SPACE}", f"key {f + 3} {ROW_SPACE} 0"]
    rd = lambda f, n: [f"dump {f} {SYM[n]} 2"]
    script = space(30) + timeout(40) + rd(55, "lives") + space(60) + timeout(110) + rd(125, "lives") + \
             space(130) + [f"poke 180 {SYM['score']} {1234 & 255}", f"poke 180 {SYM['score'] + 1} {1234 >> 8}"] + \
             timeout(181) + rd(200, "hiscore") + dump_state(200) + ["shot 200 gameover.ppm"] + \
             space(210) + dump_state(260) + rd(260, "score") + rd(260, "lives") + rd(260, "hiscore")
    d = run(script, 262)
    w = lambda f, n: d[(f, SYM[n])][0] | d[(f, SYM[n])][1] << 8
    l1, l2 = d[(55, SYM["lives"])][0], d[(125, SYM["lives"])][0]
    so, sn = state_at(d, 200), state_at(d, 260)
    ok = (l1, l2) == (2, 1) and so["state"] == 4 and w(200, "hiscore") == 1234 and \
         sn["state"] == 3 and sn["level"] == 0 and w(260, "score") == 0 and d[(260, SYM["lives"])][0] == 3 and \
         w(260, "hiscore") == 1234
    fails += not ok
    print(f"8. életek {l1},{l2}, játék vége: állapot={so['state']}, rekord={w(200, 'hiscore')}; új játék: "
          f"pálya={sn['level'] + 1} pont={w(260, 'score')} élet={d[(260, SYM['lives'])][0]} -> {'OK' if ok else 'HIBA'}")

    print("MINDEN TESZT RENDBEN" if not fails else f"{fails} HIBA")
    return fails == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
