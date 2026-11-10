# Betöltőkép – prompt a ChatGPT-hez

A kép a TVC 16 színű módjába kerül (128×240 képpont, széles képpontok). A 16 színkódból a 8-as (csak intenzitás) a gépen és az ep128emu-ban fekete, így 15 különböző szín van. A nem világos színek az emulátorban 4/7 fényerejűek (`#92`).

```
Készíts egy betöltőképet (címképet) egy 8 bites retro számítógépes játékhoz.

A játék címe Árnyékjárás. Egy csempész egy fallal körülvett régi magyar kisvárosban
(kockakövek, cserepes háztetők, templomtorony, városkapu) három csomagot próbál
kijuttatni, mielőtt este 6-kor bezárják a kaput. Az őrök csak a napsütésben látnak,
ezért az árnyékban kell osonnia. A játék lényege, hogy a napállással vándorolnak az árnyékok.

Jelenet: késő délután, a nap alacsonyan áll, és hosszú, éles, átlós árnyékokat vet az
utcára. Az előtérben egy csuklyás, köpenyes alak lapul egy ház árnyékában a fal mellett,
a hóna alatt egy zsinórral átkötött csomaggal. Tőle néhány lépésre egy napsütötte tér
kezdődik, ott egy alabárdos őr járőrözik piros kabátban. A háttérben a városfal és a
kapu toronnyal, mögötte templomtorony, órával. Az ég meleg sárga.

Hangulat: feszült, kalandos rejtőzködés, nem horror. A fény és az árnyék nagy, éles,
tiszta foltokban váltakozzon: ez a kép fő motívuma. A napos felületek sárgák és
sötétsárgák, az árnyékok sötétkékek legyenek, ahogy a játékban is.

Kompozíció: fekvő, 4:3 arányú kép. Ha a 4:3 nem lehetséges, készítsd 3:2-ben, és a fontos
részek a középső 4:3-as területen legyenek. A kép felső ötöde legyen egyszínű égbolt,
mindenféle rajz nélkül, mert oda kerül majd a cím. Ne írj a képre semmilyen szöveget,
betűt, számot vagy logót (az óra számlapjára se).

Technikai követelmények. Ez nagyon fontos, mert a képet egy Videoton TV Computer 16 színű
képernyőjére konvertálom, amelynek felbontása mindössze 128×240 képpont:
- Pixel art stílus nagy, tiszta, egyszínű foltokkal és erős, jól olvasható sziluettekkel.
- Vízszintesen nagyon kevés részlet férhet el: semmi ne legyen keskenyebb a képszélesség
  százada körülinél. Ne legyenek vékony függőleges vonalak, apró minták, textúrák.
- Ne legyen színátmenet, élsimítás, zaj, elmosás, ragyogás vagy tükröződés. Árnyékolásra
  legfeljebb néhány helyen egyszerű, kétszínű sakktábla-raszter használható.
- Kizárólag ezt a 15 színt használd, pontosan ezekkel az értékekkel:
  fekete #000000, sötétkék #000092, sötétpiros #920000, sötétbíbor #920092,
  sötétzöld #009200, sötét cián #009292, sötétsárga #929200, szürke #929292,
  kék #0000FF, piros #FF0000, bíbor #FF00FF, zöld #00FF00, cián #00FFFF,
  sárga #FFFF00, fehér #FFFFFF.
- Keret, aláírás és vízjel nélkül.
```

Ha mégis a képen legyen a cím, a „Ne írj a képre…” mondat helyett ez kerüljön bele:

```
A felső sávba nagy, vastag, szögletes, pixeles betűkkel írd ki: ÁRNYÉKJÁRÁS
(pontosan így, ékezetekkel), sárga betűk fekete körvonallal.
```

A kész képet ezután TVC formátumra kell alakítani: 128×240-re kicsinyítés, illesztés a palettára, tömörítés, és egy betöltő, amely kirajzolja. Ez a következő lépés.
