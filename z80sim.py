#!/usr/bin/env python3
"""Kis Z80 asm-értelmező tesztekhez.

Nem gépi kódot futtat, hanem a forrás utasításait értelmezi (include, equ, db, dw,
címkék), így a logika és az adatok bájtszinten ellenőrizhetők assembler nélkül.
Csak a modulokban használt utasításokat ismeri; ismeretlen utasításra hibát dob.
A T-ciklusokat a hivatalos Z80-időzítés szerint számolja.
"""
import os, re

R8 = "abcdehl"
R16 = ("bc", "de", "hl", "sp", "af")
COND = {"z": lambda f: f["z"], "nz": lambda f: not f["z"], "c": lambda f: f["c"],
        "nc": lambda f: not f["c"], "m": lambda f: f["s"], "p": lambda f: not f["s"]}


class SimError(Exception):
    pass


class Z80Sim:
    def __init__(self, files, data_base=0x9000, mem_fill=0):
        self.mem = bytearray([mem_fill] * 0x10000)
        self.sym, self.code, self.labels = {}, [], {}
        self.pending = []           # (cím, kifejezés, méret) – utólag kiértékelt dw/db
        self.dp = data_base
        for f in files:
            self._load(f)
        for addr, expr, size in self.pending:
            v = self.ev(expr)
            self.mem[addr] = v & 0xFF
            if size == 2:
                self.mem[addr + 1] = (v >> 8) & 0xFF
        self.r = dict(a=0, b=0, c=0, d=0, e=0, h=0, l=0)
        self.f = dict(z=False, c=False, s=False)
        self.sp = 0xFF00
        self.cycles = 0

    # ---------- betöltés
    def _load(self, path):
        base = os.path.dirname(path)
        for raw in open(path, encoding="utf-8"):
            line = raw.split(";")[0].rstrip()
            if not line.strip():
                continue
            m = re.match(r"^(\w+)\s+equ\s+(.+)$", line.strip(), re.I)
            if m:
                self.sym[m.group(1)] = self.ev(m.group(2))
                continue
            m = re.match(r"^(\w+):\s*(.*)$", line)
            if m:
                self._label = m.group(1)
                line = m.group(2)
                self._mark_label = True
                if not line.strip():
                    self._labelnext = m.group(1)
                    continue
            else:
                self._label = None
            name = getattr(self, "_labelnext", None) if self._label is None else self._label
            self._labelnext = None
            parts = line.strip().split(None, 1)
            op = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""
            if op == "include":
                self._load(os.path.join(base, arg.strip('"')))
                continue
            if op in ("db", "dw"):
                if name:
                    self.sym[name] = self.dp
                for a in self._split(arg):
                    self.pending.append((self.dp, a, 1 if op == "db" else 2))
                    self.dp += 1 if op == "db" else 2
                continue
            if name:
                self.labels[name] = len(self.code)
            self.code.append((op, [a.strip() for a in self._split(arg)] if arg else []))

    @staticmethod
    def _split(arg):
        out, depth, cur = [], 0, ""
        for ch in arg:
            if ch == "," and depth == 0:
                out.append(cur); cur = ""
            else:
                depth += ch == "("; depth -= ch == ")"; cur += ch
        if cur.strip():
            out.append(cur)
        return out

    def ev(self, expr):
        e = re.sub(r"\b([0-9][0-9a-fA-F]*)[hH]\b", lambda m: str(int(m.group(1), 16)), expr)
        e = re.sub(r"\b([A-Za-z_]\w*)\b", lambda m: str(self.sym[m.group(1)]) if m.group(1) in self.sym
                   else str(self.labels[m.group(1)]) if m.group(1) in self.labels else m.group(1), e)
        try:
            return int(eval(e, {"__builtins__": {}}))
        except Exception as ex:
            raise SimError(f"kifejezés: {expr!r}: {ex}")

    # ---------- regiszterek
    def g16(self, rr):
        if rr == "sp":
            return self.sp
        return (self.r[rr[0]] << 8) | self.r[rr[1]]

    def s16(self, rr, v):
        v &= 0xFFFF
        if rr == "sp":
            self.sp = v
        else:
            self.r[rr[0]], self.r[rr[1]] = v >> 8, v & 0xFF

    def rd(self, a):
        return self.mem[a & 0xFFFF]

    def wr(self, a, v):
        self.mem[a & 0xFFFF] = v & 0xFF

    def push(self, v):
        self.sp = (self.sp - 2) & 0xFFFF
        self.wr(self.sp, v); self.wr(self.sp + 1, v >> 8)

    def pop(self):
        v = self.rd(self.sp) | (self.rd(self.sp + 1) << 8)
        self.sp = (self.sp + 2) & 0xFFFF
        return v

    def src8(self, o):
        """8 bites forrás értéke és a hozzá tartozó ciklustöbblet."""
        if o in R8:
            return self.r[o], 0
        if o == "(hl)":
            return self.rd(self.g16("hl")), 3
        return self.ev(o) & 0xFF, 3

    def setzs(self, v):
        self.f["z"] = (v & 0xFF) == 0
        self.f["s"] = bool(v & 0x80)

    # ---------- futtatás
    def call(self, label, max_steps=5_000_000, **regs):
        for k, v in regs.items():
            if len(k) == 1:
                self.r[k] = v & 0xFF
            else:
                self.s16(k, v)
        pc = self.labels[label]
        self.push(0xFFFF)
        steps = 0
        while True:
            steps += 1
            if steps > max_steps:
                raise SimError("túl sok lépés")
            op, a = self.code[pc]
            pc += 1
            r = self.exec(op, a, pc)
            if r is not None:
                if r == 0xFFFF:
                    return
                pc = r

    def exec(self, op, a, pc):
        R, F = self.r, self.f
        cyc = 4
        nxt = None
        if op == "ld":
            d, s = a
            if d in R8 and s in R8:
                R[d] = R[s]
            elif d in R8 and s == "(hl)":
                R[d] = self.rd(self.g16("hl")); cyc = 7
            elif d == "a" and s in ("(de)", "(bc)"):
                R["a"] = self.rd(self.g16(s[1:3])); cyc = 7
            elif d in ("(de)", "(bc)") and s == "a":
                self.wr(self.g16(d[1:3]), R["a"]); cyc = 7
            elif d == "(hl)" and s in R8:
                self.wr(self.g16("hl"), R[s]); cyc = 7
            elif d == "(hl)":
                self.wr(self.g16("hl"), self.ev(s)); cyc = 10
            elif d in R16 and s.startswith("("):
                ad = self.ev(s[1:-1]); self.s16(d, self.rd(ad) | (self.rd(ad + 1) << 8))
                cyc = 16 if d == "hl" else 20
            elif d.startswith("(") and s in R16:
                ad = self.ev(d[1:-1]); v = self.g16(s); self.wr(ad, v); self.wr(ad + 1, v >> 8)
                cyc = 16 if s == "hl" else 20
            elif d == "a" and s.startswith("("):
                R["a"] = self.rd(self.ev(s[1:-1])); cyc = 13
            elif d.startswith("(") and s == "a":
                self.wr(self.ev(d[1:-1]), R["a"]); cyc = 13
            elif d in R16:
                self.s16(d, self.ev(s)); cyc = 10
            elif d in R8:
                R[d] = self.ev(s) & 0xFF; cyc = 7
            else:
                raise SimError(f"ld {a}")
        elif op in ("add", "adc", "sub", "sbc", "and", "or", "xor", "cp"):
            if op == "add" and a[0] == "hl":
                v = self.g16("hl") + self.g16(a[1]); F["c"] = v > 0xFFFF; self.s16("hl", v); cyc = 11
            else:
                s = a[-1]
                if op in ("add", "adc", "sbc") and a[0] != "a":
                    raise SimError(f"{op} {a}")
                x, extra = self.src8(s); cyc += extra
                A = R["a"]
                if op in ("add", "adc"):
                    v = A + x + (1 if op == "adc" and F["c"] else 0); F["c"] = v > 0xFF; R["a"] = v & 0xFF
                elif op in ("sub", "sbc", "cp"):
                    v = A - x - (1 if op == "sbc" and F["c"] else 0); F["c"] = v < 0
                    if op != "cp":
                        R["a"] = v & 0xFF
                else:
                    v = A & x if op == "and" else A | x if op == "or" else A ^ x
                    F["c"] = False; R["a"] = v & 0xFF
                self.setzs(v)
        elif op in ("inc", "dec"):
            t = a[0]; dlt = 1 if op == "inc" else -1
            if t in R16:
                self.s16(t, self.g16(t) + dlt); cyc = 6
            elif t == "(hl)":
                v = (self.rd(self.g16("hl")) + dlt) & 0xFF; self.wr(self.g16("hl"), v); self.setzs(v); cyc = 11
            else:
                R[t] = (R[t] + dlt) & 0xFF; self.setzs(R[t])
        elif op == "neg":
            v = (-R["a"]) & 0xFF; F["c"] = R["a"] != 0; R["a"] = v; self.setzs(v); cyc = 8
        elif op in ("jr", "jp"):
            if len(a) == 2:
                if COND[a[0]](F):
                    nxt = self.labels[a[1]]; cyc = 12 if op == "jr" else 10
                else:
                    cyc = 7 if op == "jr" else 10
            else:
                nxt = self.labels[a[0]]; cyc = 12 if op == "jr" else 10
        elif op == "djnz":
            R["b"] = (R["b"] - 1) & 0xFF
            if R["b"]:
                nxt = self.labels[a[0]]; cyc = 13
            else:
                cyc = 8
        elif op == "call":
            self.push(pc); nxt = self.labels[a[0]]; cyc = 17
        elif op == "ret":
            if a and not COND[a[0]](F):
                cyc = 5
            else:
                nxt = self.pop(); cyc = 10 if not a else 11
        elif op == "push":
            v = self.g16(a[0]) if a[0] != "af" else (R["a"] << 8) | (F["z"] << 6 | F["c"] | F["s"] << 7)
            self.push(v); cyc = 11
        elif op == "pop":
            v = self.pop(); cyc = 10
            if a[0] == "af":
                R["a"] = v >> 8; F["z"] = bool(v & 0x40); F["c"] = bool(v & 1); F["s"] = bool(v & 0x80)
            else:
                self.s16(a[0], v)
        elif op == "ex" and a == ["de", "hl"]:
            d, h = self.g16("de"), self.g16("hl"); self.s16("de", h); self.s16("hl", d)
        elif op == "ldir":
            n = self.g16("bc") or 0x10000
            s, d = self.g16("hl"), self.g16("de")
            for i in range(n):
                self.wr(d + i, self.rd(s + i))
            self.s16("hl", s + n); self.s16("de", d + n); self.s16("bc", 0)
            cyc = 21 * n - 5
        else:
            raise SimError(f"ismeretlen utasítás: {op} {a}")
        self.cycles += cyc
        return nxt
