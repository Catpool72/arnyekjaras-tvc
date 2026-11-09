#!/usr/bin/env python3
"""Hangeffektek ellenőrzése: a tvcsim SNDLOG naplójában a várt frekvenciák
a várt események után szólalnak meg."""
import os, re, subprocess, sys
import gen_game as GG
from test_game import SYM, SIM, CAS, HERE, ROW_SPACE, BIT_SPACE, ROW_CUR, BIT_RIGHT, BIT_DOWN


def run(script, frames):
    path = os.path.join(HERE, "_t.txt")
    open(path, "w").write("\n".join(script) + "\n")
    env = dict(os.environ, SNDLOG="1")
    out = subprocess.run([SIM, CAS, path, str(frames)], capture_output=True, text=True, cwd=HERE, env=env)
    os.remove(path)
    ev = []
    for line in out.stderr.splitlines():
        m = re.match(r"snd f(\d+) (ON |off) (\d+)Hz vol(\d+)", line)
        if m and m.group(2) == "ON ":
            ev.append((int(m.group(1)), int(m.group(3)), int(m.group(4))))
    return ev


def hz(f):
    p = GG.pitch(f)
    return int(195312.5 / (4096 - p))


def has(ev, name, after, before=10 ** 9):
    """Az effekt összes hangja (hangerő > 0) sorrendben megszólal az [after, before) ablakban."""
    want = [(hz(f), v) for _, f, v in GG.SFX[name] if v]
    seq = [(f, v) for fr, f, v in ev if after <= fr < before]
    i = 0
    for e in seq:
        if i < len(want) and e == want[i]:
            i += 1
    return i == len(want)


def main():
    fails = 0

    def check(label, ok):
        nonlocal fails
        fails += not ok
        print(f"{label}: {'OK' if ok else 'HIBA'}")

    start = [f"key 30 {ROW_SPACE} {BIT_SPACE}", f"key 32 {ROW_SPACE} 0"]

    # indítás, lépés, csomag, mind a 3 csomag, zárt kapu
    pk = SYM["pkgs"]
    ev = run(start + [
        f"key 50 {ROW_CUR} {BIT_RIGHT}", f"key 54 {ROW_CUR} 0",                       # lépés (a szignál után)
        f"poke 60 {SYM['px']} 15", f"poke 60 {SYM['py']} 1", f"poke 60 {SYM['gacc']} 0",
        f"key 62 {ROW_CUR} {BIT_RIGHT}", f"key 66 {ROW_CUR} 0",                       # (16,1): 1. csomag
    ], 100)
    check("indítási szignál", has(ev, "INTRO", 30, 50))
    check("lépés", has(ev, "STEP", 50, 60))
    check("csomag felvétele", has(ev, "PKG", 62, 100))
    ev = run(start + [
        f"poke 60 {pk + 5} 1", f"poke 60 {pk + 8} 1", f"poke 60 {SYM['got_n']} 2",   # a másik kettő megvan
        f"poke 60 {SYM['px']} 15", f"poke 60 {SYM['py']} 1", f"poke 60 {SYM['gacc']} 0",
        f"key 62 {ROW_CUR} {BIT_RIGHT}", f"key 66 {ROW_CUR} 0",
    ], 120)
    check("mind a 3 csomag", has(ev, "ALLGOT", 62, 120))

    ev = run(start + [
        f"poke 40 {SYM['px']} 28", f"poke 40 {SYM['py']} 18", f"poke 40 {SYM['gacc']} 0",
        f"key 42 {ROW_CUR} {BIT_DOWN}", f"key 46 {ROW_CUR} 0"], 80)
    check("zárt kapu", has(ev, "LOCKED", 42, 80))

    # harang 8:00-kor és dupla harang 17:00-kor (az órát előretekerjük)
    ev = run(start + [f"poke 40 {SYM['q']} 11", f"poke 40 {SYM['mm']} 9", f"poke 40 {SYM['sub']} 0",
                      f"poke 40 {SYM['gacc']} 0"], 80)
    check("harangszó egész órakor", has(ev, "BELL", 40, 80))
    ev = run(start + [f"poke 40 {SYM['q']} 65", f"poke 40 {SYM['mm']} 9", f"poke 40 {SYM['sub']} 0",
                      f"poke 40 {SYM['gacc']} 0"], 100)
    check("dupla harang 17:00-kor", has(ev, "WARN", 40, 100))
    ev = run(start + [f"poke 40 {SYM['q']} 71", f"poke 40 {SYM['mm']} 9", f"poke 40 {SYM['sub']} 0",
                      f"poke 40 {SYM['gacc']} 0"], 200)
    check("kapuzárás 18:00-kor", has(ev, "CLOSED", 40, 200))

    # várakozás: ketyegés
    ev = run(start + [f"poke 38 {SYM['gacc']} 0", f"key 40 {ROW_SPACE} {BIT_SPACE}", f"key 60 {ROW_SPACE} 0"], 70)
    ticks = sum(1 for fr, f, v in ev if 40 <= fr < 62 and (f, v) == (hz(2500), 3))
    check(f"ketyegés várakozáskor ({ticks} db)", ticks >= 5)

    # lebukás (a test_game 3. esetének helyzete) és győzelem
    ev = run(start + [f"poke 41 {SYM['px']} 18", f"poke 41 {SYM['py']} 2", f"poke 41 {SYM['gacc']} 0",
                      f"key 42 {ROW_CUR} {BIT_DOWN}", f"key 46 {ROW_CUR} 0"], 100)
    check("lebukás", has(ev, "CAUGHT", 42, 100))
    ev = run(start + [f"poke 40 {pk + 2} 1", f"poke 40 {pk + 5} 1", f"poke 40 {pk + 8} 1",
                      f"poke 40 {SYM['allgot']} 1", f"poke 40 {SYM['got_n']} 3",
                      f"poke 40 {SYM['px']} 28", f"poke 40 {SYM['py']} 18", f"poke 40 {SYM['gacc']} 0",
                      f"key 42 {ROW_CUR} {BIT_DOWN}", f"key 46 {ROW_CUR} 0"], 120)
    check("győzelmi fanfár", has(ev, "WIN", 42, 120))

    print("MINDEN HANGTESZT RENDBEN" if not fails else f"{fails} HIBA")
    return fails == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
