#!/usr/bin/env python3
"""Esc-kérdés: Esc után a játék megáll és rákérdez; más billentyűre folytatódik
(az állapotsor visszaáll), második Esc-re visszatér a BASIC-be."""
import sys
from test_game import SYM, run, ROW_SPACE, BIT_SPACE

ROW_ESC, BIT_ESC = 7, 0x08
ROW = SYM["VRAM"] + 227 * 64
start = [f"key 30 {ROW_SPACE} {BIT_SPACE}", f"key 32 {ROW_SPACE} 0", f"poke 36 {SYM['gacc']} 0"]


def clock(d, f):
    return tuple(d[(f, SYM[n])][0] for n in ("q", "mm", "sub"))


def main():
    fails = 0
    def check(label, ok):
        nonlocal fails
        fails += not ok
        print(f"{label}: {'OK' if ok else 'HIBA'}")

    dumps = lambda f: [f"dump {f} {ROW} 640", f"dump {f} {SYM['state']} 1"] + \
                      [f"dump {f} {SYM[n]} 1" for n in ("q", "mm", "sub")]
    d = run(start + dumps(38) + [f"key 40 {ROW_ESC} {BIT_ESC}", f"key 44 {ROW_ESC} 0"]
            + dumps(60) + dumps(120) + [f"key 130 {ROW_SPACE} {BIT_SPACE}", f"key 134 {ROW_SPACE} 0"]
            + dumps(150) + dumps(250), 260)
    before, asked = d[(38, ROW)], d[(60, ROW)]
    check("Esc után kérdés az állapotsorban", asked != before and any(asked))
    check("kérdés közben áll az idő", clock(d, 60) == clock(d, 120))
    check("szóközre a sor visszaáll", d[(150, ROW)] == before)
    check("szóköz után folytatódik a játék", d[(250, SYM['state'])][0] == 0 and clock(d, 250) != clock(d, 150))

    d = run(start + [f"key 40 {ROW_ESC} {BIT_ESC}", f"key 44 {ROW_ESC} 0",
                     f"key 60 {ROW_ESC} {BIT_ESC}", f"key 64 {ROW_ESC} 0"] + dumps(50) + dumps(120), 140)
    check("két Esc: kilépés (nincs több képkocka a játékban)", (50, ROW) in d and (120, ROW) not in d)
    print("ESC-TESZT RENDBEN" if not fails else f"{fails} HIBA")
    return fails == 0


if __name__ == "__main__":
    sys.exit(0 if main() else 1)
