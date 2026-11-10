#!/usr/bin/env python3
"""Betöltőkép (címkép) átalakítása TVC 16 színű képernyőre.

  python3 conv_title.py <kép.png> [előnézet.png]   ->  title.inc (tömörített képadat)

- 128x240 képpont (a TVC képpontja kb. 2,5-ször szélesebb, mint magas, ezért a 4:3-as
  kép torzítás nélkül fér rá);
- minden forrásképpontot a legközelebbi TVC-színre illeszt (ep128emu-színek), és célképpontonként
  a leggyakoribb színt veszi: így a sík foltok tiszták maradnak, nincs keveredés;
- a felső égboltsávba kerül a cím: ÁRNYÉKJÁRÁS, sötétkék betűk sötétsárga "árnyékkal";
- a legalsó 12 sor fekete sáv: ide írja a program a rekordot és a SZOKOZ feliratot;
- tömörítés: bájtos RLE (lásd rle()), a kicsomagoló az arnyek.asm-ben (unrle).
"""
import sys
from collections import Counter
from PIL import Image, ImageDraw, ImageFont

W, H = 128, 240
BAND = 12                                    # alsó fekete sáv (sor)
HI, LO = 255, 146
# TVC-szín (IGRB) -> RGB az ep128emu szerint; a 8-as (csak I) fekete, ezért kimarad
PAL = {}
for c in range(16):
    if c == 8:
        continue
    i, g, r, b = (c >> 3) & 1, (c >> 2) & 1, (c >> 1) & 1, c & 1
    v = HI if i else LO
    PAL[c] = (r * v, g * v, b * v)


def nearest(rgb):
    return min(PAL, key=lambda c: sum((a - b) ** 2 for a, b in zip(PAL[c], rgb)))


def to_tvc(img):
    """-> 240 sor x 128 színkód."""
    src = img.convert("RGB")
    sw, sh = src.size
    # 4:3-ra vágás középre (ha a kép más arányú)
    if abs(sw / sh - 4 / 3) > 0.01:
        if sw / sh > 4 / 3:
            nw = round(sh * 4 / 3)
            src = src.crop(((sw - nw) // 2, 0, (sw - nw) // 2 + nw, sh))
        else:
            nh = round(sw * 3 / 4)
            src = src.crop((0, (sh - nh) // 2, sw, (sh - nh) // 2 + nh))
        sw, sh = src.size
    # gyorsítás: a forrást először palettára képezzük egy köztes, 4x felbontású rácson
    mid = src.resize((W * 4, H * 2), Image.NEAREST)
    px = mid.load()
    cache = {}
    out = []
    for y in range(H):
        row = []
        for x in range(W):
            cnt = Counter()
            for dy in range(2):
                for dx in range(4):
                    rgb = px[x * 4 + dx, y * 2 + dy]
                    c = cache.get(rgb)
                    if c is None:
                        c = cache[rgb] = nearest(rgb)
                    cnt[c] += 1
            row.append(cnt.most_common(1)[0][0])
        out.append(row)
    return out


def title_mask():
    """A cím képpontjai 128 széles rácson: (kitöltés, árnyék) halmazok."""
    font = None
    for path in ("/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            font = ImageFont.truetype(path, 54)
            break
        except OSError:
            pass
    text = "ÁRNYÉKJÁRÁS"
    # négyzetes képpontú vászon: 128 TVC-képpont = 320 négyzetes képpont szélesség
    cw, ch = 320, 70
    canvas = Image.new("L", (cw * 4, ch * 4), 0)
    d = ImageDraw.Draw(canvas)
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    scale = min((cw * 4 - 40) / tw, (ch * 4 - 16) / th)
    font = ImageFont.truetype(font.path, int(54 * scale))
    box = d.textbbox((0, 0), text, font=font)
    tw, th = box[2] - box[0], box[3] - box[1]
    d.text(((cw * 4 - tw) // 2 - box[0], (ch * 4 - th) // 2 - box[1]), text, font=font, fill=255)
    small = canvas.resize((W, ch), Image.BOX)          # 128 x 70 sor
    fill = {(x, y) for y in range(ch) for x in range(W) if small.getpixel((x, y)) >= 110}
    shadow = {(x + 1, y + 3) for x, y in fill} - fill
    return fill, shadow, ch


def fix_clock(scr, cx=73, cy=88, rx=3.5, ry=8.5):
    """Kézi javítás: 128 képpont szélesen a toronyóra keretéből csak két ív maradt, ami
    vigyorgó arcnak látszott. Helyette zárt számlap és két mutató (háromnegyed hat)."""
    inside = lambda x, y: ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0
    cells = [(x, y) for y in range(int(cy - ry) - 1, int(cy + ry) + 2)
             for x in range(int(cx - rx) - 1, int(cx + rx) + 2) if inside(x, y)]
    for x, y in cells:
        edge = any(not inside(x + dx, y + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
        scr[y][x] = 1 if edge else 15
    for x in range(cx - 2, cx + 1):                      # nagymutató a 9-esre
        scr[cy][x] = 1
    for y in range(cy, cy + 5):                          # kismutató majdnem a 6-oson
        scr[y][cx] = 1


def compose(img):
    scr = to_tvc(img)
    fix_clock(scr)
    fill, shadow, ch = title_mask()
    top = 4
    for (x, y) in shadow:
        if 0 <= x < W and 0 <= y + top < H:
            scr[y + top][x] = 6                          # sötétsárga "árnyék"
    for (x, y) in fill:
        scr[y + top][x] = 1                              # sötétkék betű
    for y in range(H - BAND, H):
        scr[y] = [0] * W
    return scr


def spread(n):
    return (n & 1) | ((n & 2) << 1) | ((n & 4) << 2) | ((n & 8) << 3)


def to_bytes(scr):
    out = bytearray()
    for row in scr:
        for x in range(0, W, 2):
            out.append((spread(row[x]) << 1) | spread(row[x + 1]))
    return bytes(out)


def rle(data):
    """Bájtos RLE: n < 128: n+1 nyers bájt követi; n >= 128: a következő bájt (n-125)-ször (3..130);
    0xFF... nincs külön vég: a kicsomagoló pontosan len(data) bájtot ír."""
    out = bytearray()
    i, lit = 0, bytearray()

    def flush():
        nonlocal lit
        while lit:
            chunk = lit[:128]
            out.append(len(chunk) - 1)
            out.extend(chunk)
            lit = lit[128:]

    while i < len(data):
        j = i
        while j < len(data) and data[j] == data[i] and j - i < 130:
            j += 1
        if j - i >= 3:
            flush()
            out.append(125 + (j - i))
            out.append(data[i])
            i = j
        else:
            lit.append(data[i])
            i += 1
    flush()
    return bytes(out)


def unrle(packed, n):
    out = bytearray()
    i = 0
    while len(out) < n:
        c = packed[i]
        i += 1
        if c < 128:
            out.extend(packed[i:i + c + 1])
            i += c + 1
        else:
            out.extend([packed[i]] * (c - 125))
            i += 1
    return bytes(out)


def preview(scr, path):
    im = Image.new("RGB", (W * 4, H * 2))
    p = im.load()
    for y in range(H):
        for x in range(W):
            rgb = PAL.get(scr[y][x], (0, 0, 0))
            for dy in range(2):
                for dx in range(4):
                    p[x * 4 + dx, y * 2 + dy] = rgb
    im.save(path)


if __name__ == "__main__":
    scr = compose(Image.open(sys.argv[1]))
    raw = to_bytes(scr)
    packed = rle(raw)
    assert unrle(packed, len(raw)) == raw
    if len(sys.argv) > 2:
        preview(scr, sys.argv[2])
    with open("title.inc", "w") as f:
        f.write(f"; Generálta: conv_title.py ({sys.argv[1].split('/')[-1]}), "
                f"{len(raw)} bájt -> {len(packed)} bájt RLE\n")
        f.write(f"TITLE_RAW equ {len(raw)}\nTITLE_RLE:\n")
        for k in range(0, len(packed), 32):
            f.write("        db " + ",".join(str(b) for b in packed[k:k + 32]) + "\n")
    print(f"{len(raw)} bájt -> {len(packed)} bájt tömörítve")
