; ===================================================================
;  ÁRNYÉKJÁRÁS – árnyékszámító modul, Videoton TVC (Z80)
;
;  Táblavezérelt: futás közben nincs szorzás és trigonometria.
;  A napállás 10 játékpercenként vált (SunQ: 0 = 6:00 ... 71 = 17:50).
;
;  Árnyékpuffer (SHBUF): 64 bájt széles, 38 sor = 2432 bájt.
;  A 32x20-as játéktér a (MX,MY) = (16,9) pozícióban kezdődik, körülötte
;  min. 9 cellás margó van, így az árnyékvetés és a felhők VÁGÁS NÉLKÜL
;  írhatnak bele. Értékek: 0 = napos, 1 = épület/fa árnyéka, 2 = felhő,
;  3 = napos, és egy őr látja (ezt a vision.asm írja bele).
;
;  Használat egy frissítéskor (10 játékpercenként, vagy ha egy felhő
;  egész cellát lépett):
;       call ShadowClear
;       ld hl,DELIKAPU_CLOUD0 : ld d,<felhő x> : ld e,<felhő y> : call StampCloud
;       ld a,(SunQ) : ld hl,DELIKAPU_CLASS : call ShadowCast
;  Lekérdezés:
;       ld b,<x> : ld c,<y> : call IsShadow   ; A = 0/1/2, Z = napos
;
;  Szintaxis: Zilog-mnemonikok, sjasmplus / pasmo kompatibilis.
; ===================================================================

MAP_W       equ 32
MAP_H       equ 20
STRIDE      equ 64
MX          equ 16
MY          equ 9
SH_ROWS     equ 38
SH_SIZE     equ STRIDE*SH_ROWS          ; 2432
SUN_ENTRY   equ 32                      ; 6 bájt darabszám + 13 szó offset

; A puffer helyét (SHBUF, 2432 bájt) a főprogram adja meg equ-val.

; -------------------------------------------------------------------
; ShadowClear – a teljes puffer nullázása (margóval együtt)
;   ~51 000 ciklus
; -------------------------------------------------------------------
ShadowClear:
        ld hl,SHBUF
        ld de,SHBUF+1
        ld bc,SH_SIZE-1
        ld (hl),0
        ldir
        ret

; -------------------------------------------------------------------
; StampCloud – felhőmaszk rámásolása (a nem nulla bájtok íródnak)
;   be:  HL = maszk (w, h, ox, oy, majd w*h bájt)
;        D  = felhőközéppont x (előjeles cella, -11..+41 megengedett)
;        E  = felhőközéppont y
;   ront: AF, BC, DE, HL
; -------------------------------------------------------------------
StampCloud:
        push hl
        inc hl
        inc hl
        ld a,d
        sub (hl)                ; x - ox
        add a,MX
        ld c,a                  ; C = puffer-oszlop
        inc hl
        ld a,e
        sub (hl)                ; y - oy
        add a,MY
        ld l,a
        ld h,0
        add hl,hl               ; *64
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld b,0
        add hl,bc
        ld bc,SHBUF
        add hl,bc
        ex de,hl                ; DE = cél bal-felső sarka
        pop hl
        ld c,(hl)               ; C = szélesség
        inc hl
        ld a,(hl)               ; A = magasság
        inc hl
        inc hl
        inc hl                  ; HL = maszkadatok
SC_Row:
        push af
        push de
        ld b,c
SC_Col:
        ld a,(hl)
        inc hl
        or a
        jr z,SC_Skip
        ld (de),a
SC_Skip:
        inc de
        djnz SC_Col
        pop de
        ex de,hl
        push bc
        ld bc,STRIDE
        add hl,bc
        pop bc
        ex de,hl
        pop af
        dec a
        jr nz,SC_Row
        ret

; -------------------------------------------------------------------
; ShadowCast – épületek, fák és a városfal árnyékának vetése
;   be:  A  = napállás-kvantum (0..71)
;        HL = pálya osztálytérképe (32x20 bájt, 0 = nem vet árnyékot,
;             1..5 = magasságosztály)
;   ront: AF, BC, DE, HL
;
;   Belső ciklus offsetenként ~95 ciklus, kritikus úton nincs IX/IY.
; -------------------------------------------------------------------
ShadowCast:
        push hl
        ld l,a
        ld h,0
        add hl,hl               ; *32
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld de,SUNTAB
        add hl,de
        ld (SC_CntPtr),hl       ; darabszámok osztályonként
        ld de,6
        add hl,de
        ld (SC_OffPtr),hl       ; offsetlista
        pop de                  ; DE = osztálytérkép
        ld hl,SHBUF+MY*STRIDE+MX
        ld c,MAP_H
CastRow:
        ld b,MAP_W
CastCol:
        ld a,(de)
        or a
        jr z,CastNext
        push bc
        push de
        push hl
        ld hl,(SC_CntPtr)
        dec a
        add a,l
        ld l,a
        jr nc,CastNoCarry
        inc h
CastNoCarry:
        ld a,(hl)               ; A = offsetek száma ennél az osztálynál
        pop hl
        or a
        jr z,CastDone
        ld b,a
        ld de,(SC_OffPtr)
        ld c,1                  ; árnyékjelölő
CastOff:
        push hl                 ; HL = a vetítő cella címe
        ex de,hl                ; HL = offsetmutató, DE = cella
        ld a,(hl)
        inc hl
        add a,e
        ld e,a
        ld a,(hl)
        inc hl
        adc a,d
        ld d,a                  ; DE = cella + offset
        ld a,c
        ld (de),a
        ex de,hl                ; DE = offsetmutató
        pop hl                  ; HL = cella
        djnz CastOff
CastDone:
        pop de
        pop bc
CastNext:
        inc de
        inc hl
        djnz CastCol
        ld a,l                  ; következő sor: +64-32
        add a,STRIDE-MAP_W
        ld l,a
        jr nc,CastRowNC
        inc h
CastRowNC:
        dec c
        jr nz,CastRow
        ret

SC_CntPtr:  dw 0
SC_OffPtr:  dw 0

; -------------------------------------------------------------------
; IsShadow – egy játéktéri cella állapota
;   be:  B = x (0..31), C = y (0..19)
;   ki:  A = 0 napos / 1 árnyék / 2 felhő / 3 napos és őr látja, Z = napos, nem látott
;   ront: DE, HL
; -------------------------------------------------------------------
IsShadow:
        ld a,c
        add a,MY
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,b
        add a,MX
        ld e,a
        ld d,0
        add hl,de
        ld de,SHBUF
        add hl,de
        ld a,(hl)
        or a
        ret

