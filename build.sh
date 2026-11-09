#!/bin/sh
# Build: táblák -> asm -> CAS
set -e
cd "$(dirname "$0")"
SJ=${SJASMPLUS:-sjasmplus}
python3 gen_tables.py
python3 gen_game.py
$SJ --nologo --sym=arnyek.sym --lst=arnyek.lst arnyek.asm
python3 mkcas.py arnyek.bin arnyek.cas
