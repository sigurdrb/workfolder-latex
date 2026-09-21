# Halloween-bursdagsinvitasjon for Sander

Fire sider i A5 stående (148,5 × 210 mm), laget for **ett A4-ark liggende, brettet loddrett på midten** — altså et kort som åpnes som en bok.

| Fil | Hva det er |
| --- | --- |
| `invitasjon.tex` | Selve invitasjonen. 4 sider i leserekkefølge: forside, program, godt å vite, bakside. |
| `invitasjon-utskrift.tex` | Samme innhold montert på ett A4-ark (2 sider), klart til tosidig utskrift. |

## Bygge

```
pdflatex invitasjon.tex
pdflatex invitasjon.tex
pdflatex invitasjon-utskrift.tex
pdflatex invitasjon-utskrift.tex
```

**Begge** filene må kjøres to ganger. De bruker TikZ `remember picture` med
`current page`, og etter første kjøring er sideposisjonen ennå ukjent — da
havner innholdet feil på arket. Symptomet på utskriftsversjonen er nesten
blanke sider med en tynn fargestripe øverst.

`invitasjon.pdf` må være ferdig bygget før utskriftsversjonen, som henter
sidene derfra.

## Skrive ut og brette

1. Skriv ut `invitasjon-utskrift.pdf` på **A4 liggende**, tosidig.
2. Velg **100 % / faktisk størrelse**, ikke «tilpass til side». Da blir formatet feil.
3. Brett arket loddrett på midten, med forsiden ut. Kortet åpnes da mot høyre,
   med programmet til venstre og praktisk info til høyre.

Sidene ligger slik på arket:

| | Venstre halvdel | Høyre halvdel |
| --- | --- | --- |
| Arkets forside | bakside | forside |
| Arkets bakside | program | praktisk info |

### Hvis utsiden kommer opp ned i forhold til innsiden

Det er dupleks-vendingen. Vending på kortsiden og på langsiden gir akkurat
180° forskjell mellom arkets to sider, og hvilken som er riktig varierer
mellom skriverdrivere. Velg **én** av disse, ikke begge:

- Bytt vending (kortside ↔ langside) i skriverdialogen, og sett
  `\kompenser` til `0` øverst i `invitasjon-utskrift.tex`.
- La skriverinnstillingen stå, og sett `\kompenser` til `1`. Da snus
  innsiden 180° i selve PDF-en i stedet.

`\kompenser` står på `1` nå, fordi skriveren som ble brukt trengte det.

Med `\kompenser = 1` ser **side 2 av `invitasjon-utskrift.pdf` opp ned ut på
skjermen**. Det er meningen — den snuingen opphever skriverens egen.

### Hvit ramme rundt utskriften

Det er normalt. De fleste kontorskrivere kan ikke printe helt ut i papirkanten
— typisk 4–8 mm forsvinner. «Actual size» hindrer skalering (og det er riktig
valg, ellers treffer ikke bretten midten), men den kan ikke få skriveren til å
printe der den fysisk ikke når.

Designet er derfor lagt opp med en **sikker sone på 1 cm**: bakgrunnene blør
med vilje helt ut i kanten, men alt som betyr noe — rammer, tekst, figurer —
holdes minst 1 cm inn. Du får altså en hvit kant, men **ingenting blir
beskåret bort**.

Flytter du på noe i `invitasjon.tex`, hold deg innenfor x: 1,0–13,85 og
y: 1,0–20,0.

Vil du ha ekte kant-til-kant, må du enten slå på «borderless» i skriveren
(mange blekkskrivere har det) eller skrive ut på A3 og beskjære ned til A4.

## Endre tekst

Feltene øverst i `invitasjon.tex` er ment å endres:

```latex
\newcommand{\bursdagsbarn}{Sander}
\newcommand{\adresse}{Solbakken 24}
\newcommand{\dagdato}{lørdag 31. oktober}
\newcommand{\starttid}{kl. 16.00}
\newcommand{\svarfrist}{så snart som mulig}
\newcommand{\kontakt}{Sigurd Rød Brekk, mobil 932 80 515}
```

Programpostene ligger i `\foreach`-lista på siden «Program», og punktene under
«Praktisk info» i `\foreach`-lista på neste side.

Sidene tegnes som TikZ-lerret med origo nede til venstre og mål i cm.
`\sidebredde` er 14,85, `\sidehoyde` er 21, og `\midt` (7,425) brukes til å
sentrere. Alle koordinater i sidene er absolutte, så bytter du sideformat må
de settes om.
