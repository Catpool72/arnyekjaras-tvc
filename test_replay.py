#!/usr/bin/env python3
"""A megoldó útvonalának végigjátszása a kész CAS-on, a tvcsim-ben.

Minden pályán: a megoldó leggyorsabb útját billentyűleütésekké alakítja
(lépés: irány 2 körig, 5 körönként; várakozás: szóköz 1 körig). Az események a
főciklus köreihez kötöttek (tvcsim ITER=1), mert a játék ideje is körönként halad,
akárcsak a megoldó egységei; nehéz számítás közben így sem veszik el leütés.
és ellenőrzi, hogy a játék tényleg kijut-e. A 2. és 3. pályánál az előzőt
"megnyertnek" jelöljük, így nem kell azokat is végigjátszani.
"""
import sys
import solver as S
from test_game import run, dump_state, state_at, SYM, ROW_SPACE, BIT_SPACE, ROW_CUR

DIRS = {(1, 0): 0x20, (-1, 0): 0x40, (0, -1): 0x02, (0, 1): 0x04}
START = 31           # az indítás köre (szóköz 1 körig, hogy ne kezdjen várakozással)


def script_for(idx, path):
    sc = []
    if idx:
        # az előző pályát "megnyertnek" jelöljük, a szóköz így a kívánt pálya bevezetőjét hozza
        sc += [f"poke 14 {SYM['level']} {idx - 1}", f"poke 14 {SYM['state']} 1",
               f"key 20 {ROW_SPACE} {BIT_SPACE}", f"key 21 {ROW_SPACE} 0"]
        f = 60
    else:
        f = START - 1
    sc += [f"key {f} {ROW_SPACE} {BIT_SPACE}", f"key {f + 1} {ROW_SPACE} 0"]
    f += 1
    for a, b in zip(path, path[1:]):
        if a[1:3] == b[1:3]:
            sc += [f"key {f} {ROW_SPACE} {BIT_SPACE}", f"key {f + 1} {ROW_SPACE} 0"]
            f += 1
        else:
            bit = DIRS[(b[1] - a[1], b[2] - a[2])]
            sc += [f"key {f} {ROW_CUR} {bit}", f"key {f + 2} {ROW_CUR} 0"]
            f += S.MOVE
    return sc, f


def main():
    fails = 0
    for idx in range(len(S.G.LEVELS)):
        r = S.solve(idx)
        sc, end = script_for(idx, r["path"])
        sc += dump_state(end + 20) + [f"shot {end + 20} replay{idx + 1}.ppm",
                                      f"dump {end + 20} {SYM['score']} 3"]
        d = run(sc, end * 8 + 400, iters=True)
        st = state_at(d, end + 20)
        sb = d[(end + 20, SYM["score"])]
        got_score = sb[0] | sb[1] << 8
        want_score, lit = S.path_score(r)
        ok = st["state"] == 1 and st["level"] == idx and got_score == want_score
        fails += not ok
        print(f"{r['lv'].E['title']}: megoldó útja {len(r['path']) - 1} lépésben, a TVC-n: "
              f"állapot={st['state']} pálya={st['level'] + 1} hely=({st['px']},{st['py']}) "
              f"idő q={st['q']}, pont {got_score} (várt {want_score}, {lit} napos lépés) -> {'KIJUTOTT' if ok else 'HIBA'}")
    print("MINDEN VÉGIGJÁTSZÁS RENDBEN" if not fails else f"{fails} HIBA")
    return fails == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
