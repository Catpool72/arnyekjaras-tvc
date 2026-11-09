#!/usr/bin/env python3
"""Árnyékjárás TVC – grafika, font és pályaadatok generálása (game.inc).

16 színű mód: 128x240 képpont, soronként 64 bájt, bájtonként 2 képpont.
A bal képpont a páratlan bitekben (b7=I, b5=G, b3=R, b1=B), a jobb a párosakban
(ep128emu tvcvideo.cpp: videoByte & 0xAA / & 0x55).
Egy pályacella 4x10 képpont = 2 bájt x 10 sor, így a 32x20-as pálya 128x200,
alatta 40 sornyi kijelző.
"""
import os
import gen_tables as G

HERE = os.path.dirname(os.path.abspath(__file__))

# színkód: I G R B
PAL = dict(k=0, n=1, m=2, p=3, g=4, t=5, o=6, s=7, d=8, b=9, r=10, M=11, G=12, c=13, y=14, w=15)


def spread(n):
    return (n & 1) | ((n & 2) << 1) | ((n & 4) << 2) | ((n & 8) << 3)


def pair(left, right):
    return (spread(left) << 1) | spread(right)


def enc_tile(rows):
    assert len(rows) == 10 and all(len(r) == 4 for r in rows), rows
    out = []
    for r in rows:
        c = [PAL[ch] for ch in r]
        out += [pair(c[0], c[1]), pair(c[2], c[3])]
    return out


def over(base, spr, remap=None):
    remap = remap or {}
    return ["".join(b if s == "." else remap.get(s, s) for b, s in zip(br, sr)) for br, sr in zip(base, spr)]


LIT = ["oooo", "oyoo", "oooo", "oooo", "oooo", "oooo", "ooyo", "oooo", "oooo", "oooo"]
SHD = [r.replace("o", "n").replace("y", "b") for r in LIT]
CLD = ["nnnn", "ntnn", "nnnn", "nnnt", "nnnn", "tnnn", "nnnn", "nntn", "nnnn", "nnnn"]
SEEN = ["roro" if i % 2 == 0 else "oror" for i in range(10)]
GROUNDS = [LIT, SHD, CLD, SEEN]
WALL = ["dddk", "dddk", "dddk", "kkkk", "dkdd", "dkdd", "dkdd", "kkkk", "dddk", "dddk"]


def roof(b, hi, lo, h):
    rows = []
    for r in range(10):
        row = ""
        for c in range(4):
            if r == 0 or c == 0:
                ch = hi
            elif r == 9 or c == 3:
                ch = lo
            elif h > 1 and r in (4, 5) and c in (1, 2):
                ch = lo
            elif h == 4 and r == 2 and c in (1, 2):
                ch = "y"
            else:
                ch = b
            row += ch
        rows.append(row)
    return rows


GATE = ["tttt"] + ["tkkt"] * 9
GATE_OPEN = ["cccc"] + ["ckkc"] * 9
PKG = ["....", "kkkk", "kyok", "kyok", "kook", "kyok", "kyok", "kkkk", "....", "...."]
PLAYER = [".ww.", ".ww.", "cccc", "cccc", ".cc.", ".cc.", ".cc.", "c..c", "c..c", "...."]
GUARD = [".yy.", ".ww.", "rrrr", "rrrr", ".rr.", ".rr.", ".rr.", "r..r", "r..r", "...."]
TREE = [".gg.", "gGgg", "gGgg", "gggg", "gggg", ".gg.", "..m.", "..m.", "....", "...."]

# csempeazonosítók (arnyek.asm-mel egyezően)
T_WALL, T_ROOF1, T_GATE, T_GATE_OPEN = 4, 5, 10, 11
E_PKG, E_PLAYER, E_GUARD, E_TREE = 16, 20, 24, 28


def tiles():
    t = [None] * 32
    for g, gr in enumerate(GROUNDS):
        t[g] = gr
        t[E_PKG + g] = over(gr, PKG)
        dim = g in (1, 2)
        t[E_PLAYER + g] = over(gr, PLAYER, {"w": "s", "c": "t"} if dim else None)
        t[E_GUARD + g] = over(gr, GUARD)
        t[E_TREE + g] = over(gr, TREE)
    t[T_WALL] = WALL
    t[5] = roof("s", "w", "d", 1)
    t[6] = roof("m", "r", "k", 2)
    t[7] = roof("p", "M", "k", 3)
    t[8] = roof("t", "c", "k", 4)
    t[T_GATE] = GATE
    t[T_GATE_OPEN] = GATE_OPEN
    for i in range(32):
        if t[i] is None:
            t[i] = ["kkkk"] * 10
    return t


# ---- 3x5 font (ékezet nélkül), karakterek 32..95
F = {
    " ": "... ... ... ... ...", "!": ".#. .#. .#. ... .#.", ".": "... ... ... ... .#.",
    ":": "... .#. ... .#. ...", "-": "... ... ### ... ...", "/": "..# ..# .#. #.. #..",
    "0": "### #.# #.# #.# ###", "1": ".#. ##. .#. .#. ###", "2": "### ..# ### #.. ###",
    "3": "### ..# .## ..# ###", "4": "#.# #.# ### ..# ..#", "5": "### #.. ### ..# ###",
    "6": "### #.. ### #.# ###", "7": "### ..# .#. .#. .#.", "8": "### #.# ### #.# ###",
    "9": "### #.# ### ..# ###",
    "A": "### #.# ### #.# #.#", "B": "##. #.# ##. #.# ##.", "C": "### #.. #.. #.. ###",
    "D": "##. #.# #.# #.# ##.", "E": "### #.. ##. #.. ###", "F": "### #.. ##. #.. #..",
    "G": "### #.. #.# #.# ###", "H": "#.# #.# ### #.# #.#", "I": "### .#. .#. .#. ###",
    "J": "..# ..# ..# #.# ###", "K": "#.# #.# ##. #.# #.#", "L": "#.. #.. #.. #.. ###",
    "M": "#.# ### ### #.# #.#", "N": "##. #.# #.# #.# #.#", "O": "### #.# #.# #.# ###",
    "P": "### #.# ### #.. #..", "Q": "### #.# #.# ### ..#", "R": "### #.# ##. #.# #.#",
    "S": "### #.. ### ..# ###", "T": "### .#. .#. .#. .#.", "U": "#.# #.# #.# #.# ###",
    "V": "#.# #.# #.# #.# .#.", "W": "#.# #.# ### ### #.#", "X": "#.# #.# .#. #.# #.#",
    "Y": "#.# #.# .#. .#. .#.", "Z": "### ..# .#. #.. ###",
}


def font():
    out = []
    for code in range(32, 96):
        rows = F.get(chr(code), F[" "]).split()
        for r in rows:
            out.append(sum(8 >> i for i, ch in enumerate(r) if ch == "#"))
    return out


# ---- pályák kiegészítő adatai (a demóval azonosak)
EXTRA = {
    "DELIKAPU": dict(title="1. DELI KAPU", start=(1, 1), q0=(7 * 60 - G.Q_FIRST) // 10,
                     pkg=[(16, 1), (14, 7), (29, 14)], cloud_x=[-4.0],
                     paths=[(False, [(13, 9), (22, 9)]), (False, [(22, 4), (22, 16)]), (False, [(2, 12), (10, 12)])]),
    "PIACTER": dict(title="2. PIACTER", start=(1, 18), q0=(8 * 60 - G.Q_FIRST) // 10,
                    pkg=[(27, 1), (4, 7), (16, 9)], cloud_x=[-6.0, 12.0],
                    paths=[(True, [(11, 7), (19, 7), (19, 12), (11, 12)]), (False, [(1, 6), (1, 13)]),
                           (False, [(13, 2), (22, 2)]), (False, [(25, 6), (25, 13)])]),
    "VARUDVAR": dict(title="3. VARUDVAR", start=(1, 10), q0=(12 * 60 - G.Q_FIRST) // 10,
                     pkg=[(27, 4), (15, 14), (4, 13)], cloud_x=[14.0, 8.0, 20.0],
                     paths=[(True, [(12, 6), (19, 6), (19, 13), (12, 13)]), (False, [(2, 4), (2, 15)]),
                            (False, [(24, 5), (29, 5)]), (False, [(25, 8), (25, 14), (29, 14)])]),
}
ROOF_OF_CLASS = {1: 5, 3: 6, 4: 7, 5: 8}


def base_map(L):
    hgt = G.height_map(L)
    out = []
    for y in range(G.H):
        for x in range(G.W):
            if (x, y) == tuple(L["gate"]):
                out.append(T_GATE)
            elif x in (0, G.W - 1) or y in (0, G.H - 1):
                out.append(T_WALL)
            elif hgt[y][x] == 1.4:
                out.append(1)                      # fa: talaj + fa
            elif hgt[y][x]:
                out.append(ROOF_OF_CLASS[G.HEIGHT_CLASS[hgt[y][x]]])
            else:
                out.append(0)
    return out


def bar():
    """Napszak-sáv: 64 bájt, bájtonként 2 egyforma képpont."""
    out = []
    for c in range(64):
        col = "n" if c < 13 else "o" if c < 23 else "y" if c < 41 else "o" if c < 51 else "m"
        out.append(pair(PAL[col], PAL[col]))
    return out


# ---- hangeffektek: (képkocka, Hz, hangerő 0..15); f = 195312,5 / (4096 - érték)
SFX = {
    "STEP":   [(1, 300, 4)],
    "TICK":   [(1, 2500, 3)],
    "BELL":   [(2, 880, 13), (3, 880, 11), (4, 880, 9), (6, 880, 6), (8, 880, 3)],
    "WARN":   [(2, 660, 13), (3, 660, 10), (4, 660, 6), (4, 660, 0),
               (2, 660, 13), (3, 660, 10), (4, 660, 6), (8, 660, 3)],
    "CLOSED": [(4, 196, 14), (6, 196, 10), (8, 196, 6), (4, 196, 0), (4, 196, 14), (6, 196, 10),
               (8, 196, 6), (4, 196, 0), (4, 196, 14), (8, 196, 10), (16, 196, 5)],
    "PKG":    [(2, 784, 12), (2, 988, 12), (2, 1175, 12), (4, 1568, 12)],
    "ALLGOT": [(3, 1047, 12), (3, 1319, 12), (3, 1568, 12), (3, 2093, 13), (8, 2637, 13)],
    "LOCKED": [(4, 147, 11), (6, 131, 10)],
    "CAUGHT": [(4, 784, 13), (4, 622, 13), (4, 523, 12), (12, 392, 11)],
    "WIN":    [(4, 523, 13), (4, 659, 13), (4, 784, 13), (10, 1047, 14), (4, 784, 12), (14, 1047, 14)],
    "INTRO":  [(3, 392, 10), (3, 523, 10), (6, 659, 11)],
}


def pitch(f):
    return max(0, min(4094, int(round(4096 - 195312.5 / f))))


def sfx():
    o = []
    for name, steps in SFX.items():
        o.append(f"SFX_{name}:")
        for fr, f, v in steps:
            p = pitch(f)
            o.append(f"        db {fr},${p & 255:02X},${p >> 8:02X},{v}   ; {f} Hz")
        o.append("        db 0")
    return "\n".join(o)


def db(vals, per=16):
    vals = list(vals)
    return "\n".join("        db " + ",".join(str(v) for v in vals[i:i + per]) for i in range(0, len(vals), per))


def gen():
    o = ["; Generálta: gen_game.py  –  ne szerkeszd kézzel", ""]
    o.append("TILES:  ; 32 csempe x 20 bájt (2 bájt x 10 sor)")
    for i, t in enumerate(tiles()):
        o.append(f"; {i}")
        o.append(db(enc_tile(t), 20))
    o.append("FONT:   ; 3x5, karakterek 32..95, soronként 4 bit (b3 = bal)")
    o.append(db(font(), 20))
    o.append("BARGFX: ; napszak-sáv, 64 bájt")
    o.append(db(bar()))
    o.append(f"QCOL:   ; napállás-kvantum (0..{G.Q_COUNT}) -> sáv oszlopa")
    o.append(db([(q * 7) // 8 for q in range(G.Q_COUNT + 1)]))
    o.append(sfx())
    o.append("LEVEL_TAB:")
    o.append("        dw " + ",".join(f"{L['name']}_DATA" for L in G.LEVELS))
    o.append(f"LEVEL_COUNT equ {len(G.LEVELS)}")
    for L in G.LEVELS:
        p, E = L["name"], EXTRA[L["name"]]
        o.append(f"{p}_BASE:  ; 32x20 csempe-alap (0 talaj, 1 fa, egyébként csempeazonosító)")
        o.append(db(base_map(L), 32))
        o.append(f"{p}_DATA:")
        o.append(f"        dw {p}_CLASS,{p}_BASE,{p}_TITLE")
        o.append(f"        db {E['start'][0]},{E['start'][1]},{L['gate'][0]},{L['gate'][1]},{E['q0']}")
        o.append(f"        db {len(E['pkg'])}," + ",".join(f"{x},{y}" for x, y in E["pkg"]))
        o.append(f"        db {len(L['clouds'])}")
        for n, (c, x) in enumerate(zip(L["clouds"], E["cloud_x"])):
            o.append(f"        dw {p}_CLOUD{n}")
            o.append(f"        db {c['y']}")
            o.append(f"        dw {int(round(x * 256)) & 0xFFFF}")
            o.append(f"        db {-int(-c['rx'] // 1)}")      # ceil(rx)
        o.append(f"        db {len(E['paths'])}")
        for loop, pts in E["paths"]:
            o.append(f"        db {1 if loop else 0},{len(pts)}," + ",".join(f"{x},{y}" for x, y in pts))
        o.append(f'{p}_TITLE: db "{E["title"]}",0')
    return "\n".join(o) + "\n"


def preview(path):
    """A csempék előnézete PPM-ben (8x nagyítás vízszintesen, 4x függőlegesen)."""
    rgb = lambda n: tuple((255 if n & 8 else 170) * bool(n & m) for m in (2, 4, 1)) if n != 8 else (85, 85, 85)
    ts = tiles()
    W, H = 8 * 4 * 8, 4 * 10 * 4
    px = [[(0, 0, 0)] * W for _ in range(H)]
    for i, t in enumerate(ts):
        ox, oy = (i % 8) * 32, (i // 8) * 40
        for r in range(10):
            for c in range(4):
                for dy in range(4):
                    for dx in range(8):
                        px[oy + r * 4 + dy][ox + c * 8 + dx] = rgb(PAL[t[r][c]])
    with open(path, "wb") as f:
        f.write(f"P6 {W} {H} 255\n".encode())
        for row in px:
            f.write(bytes(v for p in row for v in p))


if __name__ == "__main__":
    open(os.path.join(HERE, "game.inc"), "w").write(gen())
    print("game.inc kész")
