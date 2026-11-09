;=============================================================================
; ÁRNYÉKJÁRÁS  –  Videoton TV-Computer 64K, 16 színű mód (128x240)   v02
; Z80 @ 3.125 MHz, sjasmplus.  Indítás: 10 PRINT USR(6659), automatikusan.
;
; Memória (lapozás $90 = U0 | U1 | VID | U3):
;   $19EF-       BASIC betöltő, kód, táblák (U0 -> U1, < $8000)
;   $8000-$BBFF  képernyő: 64 bájt/sor, 240 sor; a pálya 32x20 cella, 4x10 képpont
;   $C000-       árnyékpuffer, takarási térkép, csempe-alap, kívánt és kirajzolt
;                csempék, változók, verem (U3)
; A megszakítások tiltva, a képkocka-ütemezés a $59-es port 4. bitjét figyeli.
;=============================================================================

        DEVICE NOSLOT64K

VRAM        equ $8000
P_SAVE      equ $0003
PORT03      equ $0B11           ; ROM-másolatok a kilépéshez
PORT05      equ $0B12
PORT06      equ $0B13
INKV        equ $0B4D
PAPERV      equ $0B4E
BORDERV     equ $0B4F
MAP_GAME    equ $90

SHBUF       equ $C000           ; 64x38, árnyék + látómező (shadow.asm, vision.asm)
TERRAIN     equ $CA00           ; 64x38, takarás
BASEBUF     equ $D400           ; 32x20, a pálya csempe-alapja
DESIRED     equ $D700           ; 32x20, ennek kellene a képernyőn lennie  (= BASEBUF + $300)
SHOWN       equ $DA00           ; 32x20, ez van most kirajzolva            (= DESIRED + $300)
BSS         equ $DD00

; csempeazonosítók (gen_game.py)
T_GATE      equ 10
T_GATE_OPEN equ 11
E_PKG       equ 16
E_PLAYER    equ 20
E_GUARD     equ 24
E_TREE      equ 28

; ütemezés (képkockában, 50 Hz)
FR_MINUTE   equ 12              ; ennyi képkocka egy játékperc (várakozáskor 8x gyorsabb)
FR_GUARD    equ 22              ; őrlépés
WAIT_SPEED  equ 8
REP_FIRST   equ 9
REP_NEXT    equ 5
CLOUD_STEP  equ 13              ; felhő: 13/256 cella játékpercenként
Q_END       equ 72              ; 18:00, kapuzárás
Q_WARN      equ 66              ; 17:00-tól piros az óra

HUD_Y1      equ 202
HUD_BAR     equ 216
HUD_Y2      equ 227

; billentyűbitek: keys (alsó bájt)
K_LEFT      equ $01
K_RIGHT     equ $02
K_UP        equ $04
K_DOWN      equ $08
; keys+1
K_WAIT      equ $04             ; szóköz / tűz
K_ESC       equ $08

ST_PLAY     equ 0
ST_WON      equ 1
ST_LOST     equ 2
ST_INTRO    equ 3

;-----------------------------------------------------------------------------
; BASIC betöltő: 10 PRINT USR(6659)
;-----------------------------------------------------------------------------
        ORG $19EF
        db $0F,$0A,$00,$DD
        db " USR"
        db $96
        db "6659"
        db $95,$FF
        db 0,0,0,0,0
        ASSERT $ == 6659

;=============================================================================
start:
        di
        ld (quit_sp+1),sp
        ld a,MAP_GAME
        ld (P_SAVE),a
        out ($02),a
        ld sp,0                 ; verem az U3 tetején
        xor a
        out ($05),a             ; hang ki
        out ($03),a
        out ($00),a             ; keret: fekete
        ld a,2
        out ($06),a             ; 16 színű mód
        ld hl,BSS
        ld de,BSS+1
        ld bc,BSS_LEN-1
        ld (hl),0
        ldir
        xor a
        ld (level),a
        jp level_intro

;=============================================================================
; PÁLYAKEZDÉS
;=============================================================================
level_intro:
        call load_level
        ld a,ST_INTRO
        ld (state),a
        call redraw_all
        ld hl,(title_ptr)
        ld a,14
        ld de,txt_space
        call show_msg2
        jp main_loop

level_restart:
        call load_level
        call redraw_all
        ld hl,SFX_INTRO
        ld a,6
        call snd_play
        jp main_loop

; load_level: a (level) pálya adatainak betöltése, kezdőállapot
load_level:
        ld a,(level)
        add a,a
        ld l,a
        ld h,0
        ld de,LEVEL_TAB
        add hl,de
        ld a,(hl)
        inc hl
        ld h,(hl)
        ld l,a                  ; HL = pályaleíró
        ld e,(hl) : inc hl : ld d,(hl) : inc hl
        ld (class_ptr),de
        ld e,(hl) : inc hl : ld d,(hl) : inc hl
        push hl
        ex de,hl
        ld de,BASEBUF
        ld bc,640
        ldir
        pop hl
        ld e,(hl) : inc hl : ld d,(hl) : inc hl
        ld (title_ptr),de
        ld a,(hl) : inc hl : ld (px),a
        ld a,(hl) : inc hl : ld (py),a
        ld a,(hl) : inc hl : ld (gatex),a
        ld a,(hl) : inc hl : ld (gatey),a
        ld a,(hl) : inc hl : ld (q),a
        ; csomagok: n, (x,y)*n -> pkgs: x,y,felvéve
        ld a,(hl) : inc hl
        ld (npkg),a
        ld b,a
        ld de,pkgs
.pk:    ld a,(hl) : ld (de),a : inc hl : inc de
        ld a,(hl) : ld (de),a : inc hl : inc de
        xor a : ld (de),a : inc de
        djnz .pk
        ; felhők: n, (dw maszk, db y, dw x 8.8, db rx)*n
        ld a,(hl) : inc hl
        ld (ncloud),a
        ld b,a
        ld ix,clouds
.cl:    ld a,(hl) : ld (ix+C_MASK),a : inc hl
        ld a,(hl) : ld (ix+C_MASK+1),a : inc hl
        ld a,(hl) : ld (ix+C_Y),a : inc hl
        ld a,(hl) : ld (ix+C_X),a : inc hl
        ld a,(hl) : ld (ix+C_X+1),a : inc hl
        ld a,(hl) : ld (ix+C_RX),a : inc hl
        ld de,C_SIZE
        add ix,de
        djnz .cl
        ; őrök: n, (db loop, npts, (x,y)*npts)*n
        ld a,(hl) : inc hl
        ld (nguard),a
        ld b,a
        ld ix,guards
.gd:    ld a,(hl) : ld (ix+G_LOOP),a : inc hl
        ld a,(hl) : ld (ix+G_N),a : inc hl
        ld (ix+G_PTR),l
        ld (ix+G_PTR+1),h
        ld a,(hl) : ld (ix+G_X),a
        inc hl
        ld a,(hl) : ld (ix+G_Y),a
        dec hl
        ld (ix+G_I),1
        ld (ix+G_DIR),1
        ld a,(ix+G_N)
        add a,a
        ld e,a
        ld d,0
        add hl,de               ; a pontlista átlépése
        ld de,G_SIZE
        add ix,de
        djnz .gd
        ; futásidejű állapot
        xor a
        ld (mm),a
        ld (sub),a
        ld (gacc),a
        ld (allgot),a
        ld (msg_t),a
        ld (repcnt),a
        ld (state),a
        ld (got_n),a
        ld a,$FF
        ld (hud_status),a
        ld (hud_q),a
        ld (hud_bar_q),a
        ld (hud_got),a
        ld hl,(class_ptr)
        call TerrainBuild
        ld a,1
        ld (need_shadow),a
        ret

; redraw_all: teljes képernyő-újrarajzolás (törlés, minden cella, kijelző)
redraw_all:
        ld hl,VRAM
        ld de,VRAM+1
        ld bc,64*240-1
        ld (hl),0
        ldir
        ld hl,SHOWN
        ld de,SHOWN+1
        ld bc,639
        ld (hl),$FF
        ldir
        call update_world
        call hud_update
        xor a
        ld (skipfr),a           ; a teljes rajzolás alatt elnyelt képkockákat nem pótoljuk
        ret

;=============================================================================
; FŐCIKLUS
;=============================================================================
main_loop:
        call vsync
        call snd_tick
        call read_keys
        ld a,(knew+1)
        and K_ESC
        jp nz,quit
        ld a,(state)
        cp ST_PLAY
        jr z,.play
        ; --- nem játék: szóközre/tűzre továbblépés
        ld a,(knew+1)
        and K_WAIT
        jr z,main_loop
        ld a,(state)
        cp ST_INTRO
        jr nz,.notintro
        xor a
        ld (state),a
        ld hl,SFX_INTRO
        ld a,6
        call snd_play
        call hud_status_force
        jp main_loop
.notintro:
        cp ST_LOST
        jp z,level_restart
        ; nyert: következő pálya, az utolsó után elölről
        ld a,(level)
        inc a
        cp LEVEL_COUNT
        jr c,.nx
        xor a
.nx:    ld (level),a
        jp level_intro

.play:
        ; --- sebesség: várakozáskor 8x
        ld a,(keys+1)
        and K_WAIT
        ld a,1
        jr z,.sp
        ld a,WAIT_SPEED
.sp:    ld (speed),a

        ; --- mozgás ismétléssel
        ld a,(keys)
        and K_LEFT|K_RIGHT|K_UP|K_DOWN
        jr z,.nomove
        ld b,a
        ld a,(knew)
        and K_LEFT|K_RIGHT|K_UP|K_DOWN
        jr z,.held
        ld a,REP_FIRST
        ld (repcnt),a
        jr .domove
.held:  ld a,(repcnt)
        dec a
        ld (repcnt),a
        jr nz,.nomove
        ld a,REP_NEXT
        ld (repcnt),a
.domove:
        ld a,b
        call player_move
        ld a,(state)
        cp ST_PLAY
        jp nz,main_loop
.nomove:
        ; --- idő
        ld a,(speed)
        ld b,a
        ld a,(sub)
        add a,b
.mt:    cp FR_MINUTE
        jr c,.mtd
        sub FR_MINUTE
        push af
        call minute_tick
        pop af
        jr .mt
.mtd:   ld (sub),a
        ld a,(state)
        cp ST_PLAY
        jp nz,main_loop
        ; --- őrök
        ld a,(speed)
        ld b,a
        ld a,(gacc)
        add a,b
        cp FR_GUARD
        jr c,.gd
        sub FR_GUARD
        ld (gacc),a
        call guards_step
        ld a,1
        ld (need_vision),a
        jr .gdd
.gd:    ld (gacc),a
.gdd:
        call update_world
        call check_caught
        ld a,(msg_t)
        or a
        jr z,.nomsg
        dec a
        ld (msg_t),a
.nomsg:
        call hud_update
        jp main_loop

;=============================================================================
; JÁTÉKLOGIKA
;=============================================================================

; minute_tick: egy játékperc: óra, napállás, felhők
minute_tick:
        ld a,(speed)
        cp WAIT_SPEED
        jr nz,.notick
        ld hl,SFX_TICK
        ld a,1
        call snd_play
.notick:
        ld a,(mm)
        inc a
        cp 10
        jr c,.m
        ld a,(q)
        inc a
        ld (q),a
        cp Q_END
        jr c,.m0
        ld hl,txt_closed        ; 18:00: nincs több napállás, nem számolunk árnyékot
        call lose
        ld hl,SFX_CLOSED
        ld a,7
        jp snd_play
.m0:    ld hl,need_shadow
        ld (hl),1
        cp Q_WARN               ; 17:00: dupla harang
        ld hl,SFX_WARN
        jr z,.bell
.m6:    sub 6                   ; egész óra: q mod 6 = 0
        jr z,.bell1
        jr nc,.m6
        jr .nobell
.bell1: ld hl,SFX_BELL
.bell:  ld a,3
        call snd_play
.nobell:
        xor a
.m:     ld (mm),a
        ; felhők
        ld a,(ncloud)
        or a
        ret z
        ld b,a
        ld ix,clouds
.c:     ld a,(ix+C_X+1)
        ld c,a                  ; régi egész rész
        ld a,(ix+C_X)
        add a,CLOUD_STEP
        ld (ix+C_X),a
        ld a,(ix+C_X+1)
        adc a,0
        ld (ix+C_X+1),a
        cp c
        jr z,.cn
        ld hl,need_shadow
        ld (hl),1
        ; túlment a jobb szélen? (x - rx > 33)
        sub (ix+C_RX)
        bit 7,a
        jr nz,.cn
        cp 34
        jr c,.cn
        ld a,(ix+C_RX)          ; x = -rx-2
        add a,2
        neg
        ld (ix+C_X+1),a
        ld (ix+C_X),0
.cn:    ld de,C_SIZE
        add ix,de
        djnz .c
        ret

; player_move: A = iránybitek (az első érvényes irány számít)
player_move:
        ld bc,$FF00             ; B = dx, C = dy
        bit 0,a : jr nz,.go
        ld b,1
        bit 1,a : jr nz,.go
        ld bc,$00FF
        bit 2,a : jr nz,.go
        ld c,1
.go:    ld a,(px)
        add a,b
        ld d,a
        ld a,(py)
        add a,c
        ld e,a                  ; D,E = új hely
        push de
        ld b,d
        ld c,e
        call CellIndex
        ld de,TERRAIN
        add hl,de
        pop de
        ld a,(hl)
        or a
        ret nz                  ; fal, épület, fa
        ; kapu?
        ld a,(gatex)
        cp d
        jr nz,.nogate
        ld a,(gatey)
        cp e
        jr nz,.nogate
        ld a,(allgot)
        or a
        jr nz,.win
        ld hl,SFX_LOCKED
        ld a,4
        call snd_play
        ld hl,txt_need
        ld a,10
        ld (msg_ptr),hl
        ld (msg_col),a
        ld a,90
        ld (msg_t),a
        ret
.win:   ld a,d : ld (px),a
        ld a,e : ld (py),a
        ld a,1
        ld (need_redraw),a
        call update_world
        ld a,(level)
        inc a
        cp LEVEL_COUNT
        ld hl,txt_won
        jr c,.w1
        ld hl,txt_done
.w1:    push hl
        ld hl,SFX_WIN
        ld a,7
        call snd_play
        pop hl
        ld a,ST_WON
        ld (state),a
        ld a,12
        jp end_msg
.nogate:
        ld a,d : ld (px),a
        ld a,e : ld (py),a
        ld a,1
        ld (need_redraw),a
        ; csomag?
        ld a,(npkg)
        ld b,a
        ld hl,pkgs
        ld c,0                  ; felvett csomagok száma
.p:     ld a,(hl)
        cp d
        jr nz,.pn
        inc hl
        ld a,(hl)
        dec hl
        cp e
        jr nz,.pn
        inc hl
        inc hl
        ld (hl),1
        dec hl
        dec hl
.pn:    inc hl
        inc hl
        ld a,(hl)
        add a,c
        ld c,a
        inc hl
        djnz .p
        ld a,(got_n)
        cp c
        jr z,.nop               ; nem vett fel újat
        ld a,c
        ld (got_n),a
        ld a,(npkg)
        cp c
        jr z,.all
        ld hl,SFX_PKG
        ld a,4
        call snd_play
        jr .nop
.all:   ld a,1
        ld (allgot),a
        ld hl,SFX_ALLGOT
        ld a,5
        call snd_play
.nop:   ld hl,SFX_STEP          ; alacsony prioritás: a csomaghangot nem szakítja meg
        ld a,1
        call snd_play
        jp check_caught

; check_caught: napos, látott mezőn áll, vagy őr van mellette
check_caught:
        ld a,(state)
        cp ST_PLAY
        ret nz
        ld a,(px) : ld b,a
        ld a,(py) : ld c,a
        call IsSeen
        ld hl,txt_seen
        jr z,lose
        ld a,(nguard)
        ld b,a
        ld ix,guards
.g:     ld a,(px)
        sub (ix+G_X)
        jr nc,.ax
        neg
.ax:    ld c,a
        ld a,(py)
        sub (ix+G_Y)
        jr nc,.ay
        neg
.ay:    add a,c
        cp 2
        ld hl,txt_bump
        jr c,lose
        ld de,G_SIZE
        add ix,de
        djnz .g
        ret

; lose: HL = üzenet
lose:
        push hl
        ld hl,SFX_CAUGHT
        ld a,7
        call snd_play
        pop hl
        ld a,ST_LOST
        ld (state),a
        ld a,10
end_msg:
        push hl
        push af
        ld a,1
        ld (need_redraw),a
        call update_world
        call hud_update
        pop af
        pop hl
        ld de,txt_space
        jp show_msg2

; guards_step: minden őr egy lépés az útvonalán
guards_step:
        ld a,(nguard)
        ld b,a
        ld ix,guards
.g:     push bc
        call guard_target
        cp (ix+G_X)
        jr nz,.go
        ld a,c
        cp (ix+G_Y)
        jr nz,.go
        ; célba ért: következő pont
        ld a,(ix+G_LOOP)
        or a
        ld a,(ix+G_I)
        jr z,.pp
        inc a
        cp (ix+G_N)
        jr c,.st
        xor a
        jr .st
.pp:    add a,(ix+G_DIR)
        bit 7,a
        jr nz,.flip
        cp (ix+G_N)
        jr c,.st
.flip:  ld b,a                  ; a tartományon kívüli i
        ld a,(ix+G_DIR)
        neg
        ld (ix+G_DIR),a
        add a,a
        add a,b                 ; i = i + 2*dir(új), mint a demóban
.st:    ld (ix+G_I),a
        call guard_target
.go:    ; A = cél x, C = cél y
        cp (ix+G_X)
        jr z,.vy
        jr c,.xm
        inc (ix+G_X)
        jr .nx
.xm:    dec (ix+G_X)
        jr .nx
.vy:    ld a,c
        cp (ix+G_Y)
        jr z,.nx
        jr c,.ym
        inc (ix+G_Y)
        jr .nx
.ym:    dec (ix+G_Y)
.nx:    ld de,G_SIZE
        add ix,de
        pop bc
        djnz .g
        ld a,1
        ld (need_redraw),a
        ret

; guard_target: IX = őr -> A = pts[i].x, C = pts[i].y
guard_target:
        ld l,(ix+G_PTR)
        ld h,(ix+G_PTR+1)
        ld a,(ix+G_I)
        add a,a
        ld e,a
        ld d,0
        add hl,de
        ld a,(hl)
        inc hl
        ld c,(hl)
        ret

;=============================================================================
; VILÁG FRISSÍTÉSE: árnyék -> látómező -> kívánt csempék -> kirajzolás
;=============================================================================
update_world:
        ld a,(need_shadow)
        or a
        jr z,.ns
        xor a
        ld (need_shadow),a
        call ShadowClear
        ld a,(ncloud)
        or a
        jr z,.nc
        ld b,a
        ld ix,clouds
.c:     push bc
        ld l,(ix+C_MASK)
        ld h,(ix+C_MASK+1)
        ld d,(ix+C_X+1)
        ld e,(ix+C_Y)
        call StampCloud
        ld de,C_SIZE
        add ix,de
        pop bc
        djnz .c
.nc:    ld a,(q)
        cp Q_END
        jr c,.qok
        ld a,Q_END-1            ; a napállás-tábla 0..71
.qok:   ld hl,(class_ptr)
        call ShadowCast
        ld a,1
        ld (need_vision),a
.ns:    ld a,(need_vision)
        or a
        jr z,.nv
        xor a
        ld (need_vision),a
        call VisionClear
        ld a,(nguard)
        ld b,a
        ld ix,guards
.g:     push bc
        ld b,(ix+G_X)
        ld c,(ix+G_Y)
        call VisionGuard
        call snd_poll
        ld de,G_SIZE
        add ix,de
        pop bc
        djnz .g
        ld a,1
        ld (need_redraw),a
.nv:    ld a,(need_redraw)
        or a
        ret z
        xor a
        ld (need_redraw),a
        call build_desired
        jp sync_cells

; build_desired: a kívánt csempék (DESIRED) a csempe-alapból, az árnyékból és a szereplőkből
build_desired:
        ld de,BASEBUF
        ld hl,SHBUF+MY*STRIDE+MX
        ld c,MAP_H
.r:     ld b,MAP_W
.x:     ld a,(de)
        cp 2
        jr nc,.st               ; fal, tető, kapu: változatlan
        or a
        ld a,(hl)               ; talaj: 0 napos, 1 árnyék, 2 felhő, 3 látott
        jr z,.st
        add a,E_TREE
.st:    inc d
        inc d
        inc d
        ld (de),a               ; DESIRED = BASEBUF + $300
        dec d
        dec d
        dec d
        inc de
        inc hl
        djnz .x
        ld a,l
        add a,STRIDE-MAP_W
        ld l,a
        jr nc,.nc
        inc h
.nc:    dec c
        jr nz,.r
        ; nyitott kapu
        ld a,(allgot)
        or a
        jr z,.gc
        ld a,(gatex) : ld b,a
        ld a,(gatey) : ld c,a
        call des_addr
        ld (hl),T_GATE_OPEN
.gc:    ; csomagok
        ld a,(npkg)
        ld b,a
        ld ix,pkgs
.p:     ld a,(ix+2)
        or a
        jr nz,.pn
        push bc
        ld b,(ix+0)
        ld c,(ix+1)
        ld e,E_PKG
        call put_entity
        pop bc
.pn:    inc ix
        inc ix
        inc ix
        djnz .p
        ; játékos
        ld a,(px) : ld b,a
        ld a,(py) : ld c,a
        ld e,E_PLAYER
        call put_entity
        ; őrök
        ld a,(nguard)
        ld b,a
        ld ix,guards
.g:     push bc
        ld b,(ix+G_X)
        ld c,(ix+G_Y)
        ld e,E_GUARD
        call put_entity
        ld de,G_SIZE
        add ix,de
        pop bc
        djnz .g
        ret

; put_entity: B = x, C = y, E = szereplő-alapazonosító (+ a talaj 0..3)
put_entity:
        call des_addr
        ld a,(hl)
        and 3
        add a,e
        ld (hl),a
        ret

; des_addr: B = x, C = y -> HL = DESIRED + y*32 + x
des_addr:
        ld l,c
        ld h,0
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        add hl,hl
        ld a,l
        add a,b
        ld l,a
        ld a,h
        adc a,DESIRED/256
        ld h,a
        ret

; sync_cells: ami a DESIRED-ben más, mint a SHOWN-ban, azt kirajzolja
sync_cells:
        ld hl,VRAM
        ld de,DESIRED
        ld c,MAP_H
.r:     ld b,MAP_W
.x:     ld a,(de)
        inc d
        inc d
        inc d                   ; SHOWN = DESIRED + $300
        ex de,hl
        cp (hl)
        jr z,.same
        ld (hl),a
        ex de,hl
        dec d
        dec d
        dec d
        call draw_tile
        jr .nx
.same:  ex de,hl
        dec d
        dec d
        dec d
.nx:    inc de
        inc hl
        inc hl
        djnz .x
        push de
        ld de,64*10-64
        add hl,de
        pop de
        call snd_poll
        dec c
        jr nz,.r
        ret

; draw_tile: A = csempe, HL = képernyőcím (megőrzi BC, DE, HL)
draw_tile:
        push bc
        push de
        push hl
        ex de,hl                ; DE = cél
        ld l,a
        ld h,0
        add hl,hl
        add hl,hl
        ld b,h
        ld c,l
        add hl,hl
        add hl,hl
        add hl,bc               ; *20
        ld bc,TILES
        add hl,bc
        ld a,10
.l:     ldi
        ldi
        ex de,hl
        ld bc,62
        add hl,bc
        ex de,hl
        dec a
        jr nz,.l
        pop hl
        pop de
        pop bc
        ret

;=============================================================================
; KIJELZŐ (a pálya alatti 40 sor)
;=============================================================================
hud_update:
        ; --- óra és napszak-sáv, ha változott a negyedóra... a 10 perc vagy a perc
        ld a,(q)
        ld b,a
        ld a,(mm)
        add a,b                 ; egyszerű változásjelző (q+mm), minden percben más
        ld hl,hud_q
        cp (hl)
        jr z,.noclk
        ld (hl),a
        call draw_clock
.noclk:
        ld a,(q)
        ld hl,hud_bar_q
        cp (hl)
        jr z,.nobar
        ld (hl),a
        call draw_bar
.nobar:
        ld a,(got_n)
        ld hl,hud_got
        cp (hl)
        jr z,.nogot
        ld (hl),a
        call draw_got
.nogot:
        ; --- állapotsor (csak játék közben)
        ld a,(state)
        cp ST_PLAY
        ret nz
        ld a,(msg_t)
        or a
        jr z,.nomsg
        ld a,$80                ; üzenet látszik
        ld hl,hud_status
        cp (hl)
        ret z
        ld (hl),a
        ld hl,(msg_ptr)
        ld a,(msg_col)
        ld de,0
        jp show_msg2
.nomsg:
        ld a,(speed)
        cp 1
        ld a,4                  ; várakozás
        jr nz,.st
        ld a,(px) : ld b,a
        ld a,(py) : ld c,a
        call IsShadow           ; 0 napos, 1 árnyék, 2 felhő (3 itt már lebukás)
.st:    ld hl,hud_status
        cp (hl)
        ret z
        ld (hl),a
        add a,a
        add a,a                 ; *4: dw szöveg, db szín, db 0
        ld l,a
        ld h,0
        ld de,status_tab
        add hl,de
        ld e,(hl)
        inc hl
        ld d,(hl)
        inc hl
        ld a,(hl)
        ex de,hl
        ld de,0
        jp show_msg2

hud_status_force:
        ld a,$FF
        ld (hud_status),a
        jp hud_update

status_tab:
        dw txt_sun   : db 14,0
        dw txt_shade : db 9,0
        dw txt_cloud : db 13,0
        dw txt_sun   : db 14,0
        dw txt_wait  : db 15,0

; show_msg2: az állapotsor törlése és két szöveg egymás után
;   HL = 1. szöveg, A = szín, DE = 2. szöveg vagy 0
show_msg2:
        push de
        push hl
        call set_ink
        ld hl,VRAM+HUD_Y2*64
        ld de,VRAM+HUD_Y2*64+1
        ld bc,64*10-1
        ld (hl),0
        ldir
        pop hl
        ld de,VRAM+HUD_Y2*64
        call print_str
        pop hl
        ld a,h
        or l
        ret z
        jp print_str

draw_clock:
        ; óra = 6 + q/6, perc = (q mod 6)*10 + mm
        ld a,(q)
        ld b,6
        ld c,0
.d6:    cp 6
        jr c,.d6e
        sub 6
        inc c
        jr .d6
.d6e:   ld b,a                  ; B = q mod 6
        ld a,c
        add a,6                 ; óra
        ld c,0
.d10:   cp 10
        jr c,.d10e
        sub 10
        inc c
        jr .d10
.d10e:  add a,'0'
        ld (clk_buf+1),a
        ld a,c
        add a,'0'
        ld (clk_buf),a
        ld a,b
        add a,'0'
        ld (clk_buf+3),a
        ld a,(mm)
        add a,'0'
        ld (clk_buf+4),a
        ld a,(q)
        cp Q_WARN
        ld a,15
        jr c,.ink
        ld a,10
.ink:   call set_ink
        ld hl,clk_buf
        ld de,VRAM+HUD_Y1*64
        call print_str
        ld a,7
        call set_ink
        ld hl,(title_ptr)
        ld de,VRAM+HUD_Y1*64+14
        jp print_str

draw_got:
        add a,'0'
        ld (got_buf+7),a
        ld a,(allgot)
        or a
        ld a,14
        jr z,.i
        ld a,13
.i:     call set_ink
        ld hl,got_buf
        ld de,VRAM+HUD_Y1*64+44
        jp print_str

draw_bar:
        ld de,VRAM+HUD_BAR*64
        ld c,6
.r:     ld hl,BARGFX
        ld b,64
.x:     ld a,(hl)
        ld (de),a
        inc hl
        inc de
        djnz .x
        dec c
        jr nz,.r
        ; kapuzárás jele és a nap
        ld hl,VRAM+HUD_BAR*64+63
        ld a,$CC                ; piros
        call bar_col
        ld a,(q)
        ld l,a
        ld h,0
        ld de,QCOL
        add hl,de
        ld a,(hl)
        ld l,a
        ld h,0
        ld de,VRAM+(HUD_BAR-2)*64
        add hl,de
        ld a,$FF                ; fehér
        ld b,10
        ld de,64
.m:     ld (hl),a
        add hl,de
        djnz .m
        ret
bar_col:
        ld b,6
        ld de,64
.l:     ld (hl),a
        add hl,de
        djnz .l
        ret

;-----------------------------------------------------------------------------
; Szöveg: 3x5-ös font, cellánként 4x10 képpont (a sorok duplázva)
;-----------------------------------------------------------------------------
; set_ink: A = szín (0..15)
set_ink:
        ld l,a
        ld h,0
        ld de,SPREAD
        add hl,de
        ld a,(hl)               ; jobb képpont
        ld (ink_tbl+1),a
        add a,a
        ld (ink_tbl+2),a        ; bal képpont
        ld b,a
        ld a,(ink_tbl+1)
        or b
        ld (ink_tbl+3),a
        xor a
        ld (ink_tbl),a
        ret

; print_str: HL = 0-végű szöveg, DE = képernyőcím -> DE a szöveg utánra
print_str:
        ld a,(hl)
        or a
        ret z
        push hl
        call print_chr
        pop hl
        inc hl
        jr print_str

; print_chr: A = karakter, DE = cím; DE += 2
print_chr:
        sub 32
        ld l,a
        ld h,0
        ld b,h
        ld c,l
        add hl,hl
        add hl,hl
        add hl,bc               ; *5
        ld bc,FONT
        add hl,bc
        push de
        ld b,5
.r:     push bc
        ld a,(hl)
        inc hl
        push hl
        ld c,a
        rrca
        rrca
        and 3
        call ink_byte
        ld (de),a
        ld hl,64
        add hl,de
        ld (hl),a
        inc de
        ld a,c
        and 3
        call ink_byte
        ld (de),a
        ld hl,64
        add hl,de
        ld (hl),a
        ex de,hl
        ld de,128-1
        add hl,de
        ex de,hl
        pop hl
        pop bc
        djnz .r
        pop de
        inc de
        inc de
        ret
ink_byte:
        push hl
        ld l,a
        ld h,0
        push de
        ld de,ink_tbl
        add hl,de
        pop de
        ld a,(hl)
        pop hl
        ret

SPREAD: db 0,1,4,5,16,17,20,21,64,65,68,69,80,81,84,85
clk_buf:    db "00:00",0
got_buf:    db "CSOMAG 0/3",0

txt_space:  db " - SZOKOZ",0
txt_sun:    db "NAPON - VIGYAZZ!",0
txt_shade:  db "ARNYEKBAN",0
txt_cloud:  db "FELHO ALATT",0
txt_wait:   db "VARAKOZAS...",0
txt_need:   db "KELL MIND A 3 CSOMAG!",0
txt_seen:   db "ESZREVETT AZ OR!",0
txt_bump:   db "BELEBOTLOTT AZ OR!",0
txt_closed: db "BEZARTAK A KAPUT!",0
txt_won:    db "KIJUTOTTAL!",0
txt_done:   db "VEGIGJATSZOTTAD!",0

;=============================================================================
; RENDSZER: képkocka, billentyűzet, kilépés (a BLOKK 3D-ből)
;=============================================================================
vsync:
        ld a,(skipfr)           ; a snd_poll által már elnyelt képkocka: nem várunk
        or a
        jr z,.wait
        dec a
        ld (skipfr),a
        ret
.wait:  ld hl,3000
.w:     in a,($59)
        and $10
        jr z,.got
        dec hl
        ld a,h
        or l
        jr nz,.w
.got:   out ($07),a
        ret

; read_keys: keys = aktuális, knew = új lenyomások
read_keys:
        ld hl,(keys)
        ld (kprev),hl
        ld de,0
        ; 8. sor: fel=02 le=04 tűz=08 jobb=20 bal=40
        ld a,8 : out ($03),a : in a,($58) : cpl
        ld c,a
        bit 6,c : jr z,$+4 : set 0,e
        bit 5,c : jr z,$+4 : set 1,e
        bit 1,c : jr z,$+4 : set 2,e
        bit 2,c : jr z,$+4 : set 3,e
        bit 3,c : jr z,$+4 : set 2,d
        ; 7. sor: Esc=08 Szóköz=20
        ld a,7 : out ($03),a : in a,($58) : cpl
        ld c,a
        bit 3,c : jr z,$+4 : set 3,d
        bit 5,c : jr z,$+4 : set 2,d
        ld (keys),de
        ld hl,(kprev)
        ld a,l : cpl : and e : ld (knew),a
        ld a,h : cpl : and d : ld (knew+1),a
        ret

quit:
        call snd_stop
.rel:   call vsync
        call read_keys
        ld hl,(keys)
        ld a,h
        or l
        jr nz,.rel
        ld a,$70
        ld (P_SAVE),a
        out ($02),a
        ld a,(PORT06) : out ($06),a
        ld a,(PORT05) : out ($05),a
        ld a,(PORT03) : out ($03),a
        ld a,(BORDERV) : out ($00),a
        ld a,(PAPERV) : and 3 : add a,$60 : ld c,a
        xor a
        out (c),a
        ld a,(INKV) : and 3 : add a,$60 : ld c,a
        ld a,$55
        out (c),a
        out ($07),a
quit_sp:
        ld sp,0                 ; önmódosító: BASIC verem
        ei
        rst $30
        db $05                  ; CLS
        ret

;-----------------------------------------------------------------------------
; HANG (a BLOKK 3D-ből): egycsatornás hanggenerátor, képkockánként léptetett
; effektek. Effekt: (db képkocka, hangmagasság alsó/felső, hangerő)*, db 0.
; 4/5-ös port: 12 bites hangmagasság (5-ös b4 = hang be), 6-os: b2-b5 hangerő,
; b0-b1 videómód (itt 2 = 16 szín).
;-----------------------------------------------------------------------------
; snd_play: HL = effekt, A = prioritás (alacsonyabb nem szakít félbe magasabbat)
snd_play:
        ld e,a
        ld a,(snd_ptr+1)
        or a
        jr z,.go
        ld a,(snd_pri)
        cp e
        jr z,.go
        ret nc
.go:    ld a,e
        ld (snd_pri),a
        ld (snd_ptr),hl
        jr snd_next

; snd_tick: képkockánként egyszer
snd_tick:
        ld a,(snd_ptr+1)
        or a
        ret z
        ld hl,snd_cnt
        dec (hl)
        ret nz
snd_next:
        ld hl,(snd_ptr)
        ld a,(hl)
        or a
        jr z,snd_stop
        ld (snd_cnt),a
        inc hl
        ld a,(hl)
        out ($04),a
        inc hl
        ld a,(hl)
        or $10
        out ($05),a
        inc hl
        ld a,(hl)
        add a,a
        add a,a
        or 2                    ; hangerő + 16 színű mód
        out ($06),a
        inc hl
        ld (snd_ptr),hl
        ret

snd_stop:
        xor a
        out ($05),a
        ld a,2
        out ($06),a
        ld hl,0
        ld (snd_ptr),hl
        ret

; snd_poll: hosszú munka közben: ha eltelt egy képkocka, lép egyet a hang
;   megőrzi BC, DE, HL; rontja AF
snd_poll:
        in a,($59)
        and $10
        ret nz
        out ($07),a
        ld a,(skipfr)
        inc a
        ld (skipfr),a
        push bc
        push de
        push hl
        call snd_tick
        pop hl
        pop de
        pop bc
        ret

ShadowRowHook equ snd_poll

;=============================================================================
; MODULOK ÉS ADATOK
;=============================================================================
        include "shadow.asm"
        include "vision.asm"
        include "suntab.inc"
        include "vistab.inc"
        include "level1.inc"
        include "level2.inc"
        include "game.inc"

IMAGE_END:
        ASSERT IMAGE_END <= $8000

;=============================================================================
; VÁLTOZÓK (U3)
;=============================================================================
C_MASK      equ 0
C_Y         equ 2
C_X         equ 3               ; 8.8 előjeles, a felső bájt az egész rész
C_RX        equ 5
C_SIZE      equ 6
G_X         equ 0
G_Y         equ 1
G_I         equ 2
G_DIR       equ 3
G_LOOP      equ 4
G_N         equ 5
G_PTR       equ 6
G_SIZE      equ 8

        ORG BSS
level       ds 1
state       ds 1
px          ds 1
py          ds 1
gatex       ds 1
gatey       ds 1
q           ds 1
mm          ds 1
sub         ds 1
gacc        ds 1
speed       ds 1
repcnt      ds 1
allgot      ds 1
got_n       ds 1
need_shadow ds 1
need_vision ds 1
need_redraw ds 1
msg_t       ds 1
msg_col     ds 1
msg_ptr     ds 2
hud_status  ds 1
hud_q       ds 1
hud_bar_q   ds 1
hud_got     ds 1
class_ptr   ds 2
title_ptr   ds 2
keys        ds 2
kprev       ds 2
knew        ds 2
ink_tbl     ds 4
snd_ptr     ds 2
snd_cnt     ds 1
snd_pri     ds 1
skipfr      ds 1
npkg        ds 1
pkgs        ds 3*3
ncloud      ds 1
clouds      ds 2*C_SIZE
nguard      ds 1
guards      ds 4*G_SIZE
BSS_LEN     equ $ - BSS
        ASSERT $ < $FF00

        SAVEBIN "arnyek.bin", $19EF, IMAGE_END-$19EF
