; ===================================================================
;  ÁRNYÉKJÁRÁS – őrök látómezeje, Videoton TVC (Z80)
;
;  Az őr az 5 cellás körön belül (dx*dx+dy*dy <= 30, 97 cella) minden
;  olyan cellát lát, amely járható, NAPOS (SHBUF = 0), és a rálátást
;  nem takarja épület, fa vagy fal. A Bresenham-utak eltolás alakban
;  előre ki vannak számolva (vistab.inc, 748 bájt), mert az út csak
;  (dx,dy)-tól függ, az őr helyétől nem.
;
;  Pufferek: ugyanaz a 64 széles, margós elrendezés, mint a SHBUF-nál.
;    TERRAIN: 0 = járható, 1 = takar (épület, fa, fal, és a teljes margó)
;  A látott cellák a SHBUF-ba kerülnek 3-as értékkel (látni csak napos,
;  azaz 0 értékű cellát lehet, így ez nem ütközik az árnyékkal). Ezért
;  nem kell külön látómező-puffer, és a törlés is csak a 640 cellát nézi.
;
;  Használat:
;       pályakezdéskor:   ld hl,DELIKAPU_CLASS : call TerrainBuild
;       őrlépéskor és árnyékfrissítéskor:
;                         call VisionClear
;                         ld b,<őr x> : ld c,<őr y> : call VisionGuard   ; őrönként
;       lebukás:          ld b,<játékos x> : ld c,<játékos y> : call IsSeen ; Z = látják
;  (A közvetlen szomszédságot – "belebotlott" – a játéklogika külön nézi.)
;
;  Előfeltétel: shadow.asm és a SHBUF, TERRAIN címek (equ) a főprogramban.
;  A VISTAB táblát (vistab.inc) a főprogram illeszti be.
; ===================================================================

; -------------------------------------------------------------------
; TerrainBuild – takarási térkép a pálya osztálytérképéből
;   be:  HL = osztálytérkép (32x20, nem nulla = takar)
; -------------------------------------------------------------------
TerrainBuild:
        push hl
        ld hl,TERRAIN
        ld de,TERRAIN+1
        ld bc,SH_SIZE-1
        ld (hl),1               ; a margó mind takar
        ldir
        pop hl
        ld de,TERRAIN+MY*STRIDE+MX
        ld c,MAP_H
TB_Row:
        ld b,MAP_W
TB_Col:
        ld a,(hl)
        or a
        jr z,TB_Put
        ld a,1
TB_Put:
        ld (de),a
        inc hl
        inc de
        djnz TB_Col
        ld a,e
        add a,STRIDE-MAP_W
        ld e,a
        jr nc,TB_NC
        inc d
TB_NC:
        dec c
        jr nz,TB_Row
        ret

; -------------------------------------------------------------------
; VisionClear – az előző látómező (3-as cellák) visszaállítása napossá
;   csak a 32x20-as játéktér, ~27 000 ciklus
; -------------------------------------------------------------------
VisionClear:
        ld hl,SHBUF+MY*STRIDE+MX
        ld de,STRIDE-MAP_W
        ld c,MAP_H
VC_Row:
        ld b,MAP_W
VC_Col:
        ld a,(hl)
        cp 3
        jr nz,VC_Next
        ld (hl),0
VC_Next:
        inc hl
        djnz VC_Col
        add hl,de
        dec c
        jr nz,VC_Row
        ret

; -------------------------------------------------------------------
; CellIndex – B = x, C = y  ->  HL = (y+MY)*64 + (x+MX)
;   ront: A, DE
; -------------------------------------------------------------------
CellIndex:
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
        ret

; -------------------------------------------------------------------
; VisionGuard – egy őr látómezejének bejelölése (SHBUF = 3)
;   be:  B = őr x, C = őr y
;   ront: AF, BC, DE, HL
; -------------------------------------------------------------------
VisionGuard:
        call CellIndex
        ld (VG_Idx),hl
        ld de,VISTAB
        ld a,(de)
        inc de
        ld b,a                  ; B = célok száma
VG_Loop:
        push bc
        ld hl,(VG_Idx)
        ld a,(de)
        inc de
        add a,l
        ld l,a
        ld a,(de)
        inc de
        adc a,h
        ld h,a                  ; HL = cél indexe
        ld (VG_Tgt),hl
        ld a,(de)
        inc de
        ld b,a                  ; B = köztes cellák száma
        push de
        ld de,TERRAIN
        add hl,de
        ld a,(hl)
        or a
        jr nz,VG_SkipPop        ; a cél maga takar (vagy a pályán kívül esik)
        ld hl,(VG_Tgt)
        ld de,SHBUF
        add hl,de
        ld a,(hl)
        or a
        jr nz,VG_SkipPop        ; árnyékban van, vagy már bejelölte egy másik őr
        pop de
        ld a,b
        or a
        jr z,VG_Mark
VG_Los:
        ld hl,(VG_Idx)
        ld a,(de)
        inc de
        add a,l
        ld l,a
        ld a,(de)
        inc de
        adc a,h
        ld h,a
        push de
        ld de,TERRAIN
        add hl,de
        pop de
        ld a,(hl)
        or a
        jr nz,VG_Blocked
        djnz VG_Los
VG_Mark:
        ld hl,(VG_Tgt)
        push de
        ld de,SHBUF
        add hl,de
        pop de
        ld (hl),3
        jr VG_Next
VG_Blocked:                     ; a maradék B-1 köztes offset átugrása
        dec b
        jr z,VG_Next
VG_Skip1:
        inc de
        inc de
        djnz VG_Skip1
        jr VG_Next
VG_SkipPop:
        pop de                  ; mind a B köztes offset átugrása
        ld a,b
        or a
        jr z,VG_Next
VG_Skip2:
        inc de
        inc de
        djnz VG_Skip2
VG_Next:
        pop bc
        djnz VG_Loop
        ret

VG_Idx:     dw 0
VG_Tgt:     dw 0

; -------------------------------------------------------------------
; IsSeen – B = x, C = y  ->  Z, ha valamelyik őr látja
;   ront: A, DE, HL
; -------------------------------------------------------------------
IsSeen:
        call CellIndex
        ld de,SHBUF
        add hl,de
        ld a,(hl)
        cp 3
        ret
