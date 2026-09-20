# Halloween-bursdagsinvitasjon for Sander

Fire sider i A5 liggende (210 × 148,5 mm), laget for **ett A4-ark brettet vannrett på midten**.

| Fil | Hva det er |
| --- | --- |
| `invitasjon.tex` | Selve invitasjonen. 4 sider i leserekkefølge: forside, program, godt å vite, bakside. |
| `invitasjon-utskrift.tex` | Samme innhold montert på ett A4-ark (2 sider), klart til tosidig utskrift. |

## Bygge

```
pdflatex invitasjon.tex
pdflatex invitasjon.tex
pdflatex invitasjon-utskrift.tex
```

`invitasjon.tex` må kjøres to ganger (TikZ `remember picture`), og må bygges før
utskriftsversjonen, som henter sidene fra `invitasjon.pdf`.

## Skrive ut og brette

1. Skriv ut `invitasjon-utskrift.pdf` **tosidig, vending på langsiden**.
2. Velg **100 % / faktisk størrelse**, ikke «tilpass til side». Da blir formatet feil.
3. Legg arket med innsiden (program / godt å vite) opp, og brett øverste halvdel
   ned mot deg. Forsiden havner da riktig vei øverst, og kortet åpnes oppover.

Bakgrunnen går helt ut i kanten. De fleste kontorskrivere klarer ikke kantløs
utskrift, så regn med en smal hvit ramme med mindre du skriver ut på A3 og
beskjærer ned til A4.

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
