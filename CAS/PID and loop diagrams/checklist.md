# CAS P&ID and loop diagrams: how to re-check the set

`CAS PID and loop diagrams.tex` is meant to be the latest and best record of the CAS (Heimdall) process and
instrumentation. It is checked against its sources **on request**, not on a schedule. This file is the
procedure. Run it in full when asked to "check the P&ID".

Build: `pdflatex` twice (the sheets use `remember picture`) in this folder. MiKTeX is installed.

## Drawing rules (do not change without a reason)

- ISA-5.1 identification and symbols, ISA-5.4 loop diagrams, as in Kuphaldt *Lessons In Industrial
  Instrumentation* ch. 7 and Sands & Verhappen *A Guide to the Automation Body of Knowledge* (ISA 2018) ch. 1.
  `C:\Users\sigurd.brekk\OneDrive - ScaleAQ\Dokumenter\Litteratur\`.
- The style follows the books. The preliminary P&ID (`CAS prelim P&ID rev B.pdf`) is only a reference.
- Symbols live in `caspid.sty`: `\instr` (bubbles: field, panel, behind, shared, plc, computer, logic),
  equipment macros, line styles (`water`, `oxygen`, `oil`, `elec`, `fieldbus` = Modbus TCP/RTU, `datalink` =
  inside the PLC, `extlink` = OPC UA), `\offpage`, `\pidsheet`, and the loop helpers `\loopcolumns`,
  `\termstrip`, `\cable`, `\looptable`.
- One sheet per system, with off-page connectors that name the other sheet. Typical sheets are drawn for
  n = 1, with a table of the tags for n = 2 and 3.
- Disagreements are marked in red on the sheet (`pidcheck`) and listed on CAS-PID-950 with an id
  (A = wrong on site if not fixed, B = sources disagree / decision needed, C = documentation only).

## Sources and what to compare

| Source | Where | Compare with |
|---|---|---|
| PLC | `C:\Users\sigurd.brekk\OneDrive - ScaleAQ\CODESYS\SP22\Heimdall\git` (scaleaq/heimdall-plc); read the working branch from git (`git show origin/<branch>:<file>`, ST in `TextBlobForSerialisation`), or the IDE through the codesys MCP server, one request at a time, application PFC200_Sim only | FB.RIO.CommonRIO / InletRIO mappings and read/write quantities, PFC200_Sim ModbusRTUData, PRG.FramoDataProcessing nodes, ConfigValues ranges and defaults, InletSupervisor (LIC01, OIC01), OxyControl (PIC, FIC, I4, I5), InletControl (I1), PenControl (I6, I7) -> sheets 100-700, loop sheets, CAS-PID-900/901 |
| Cabinet drawings | `...\CAS - Electrical Installation & Power Generator - Tegninger` (792.001, 792.002, 874.001, 874.004, 875.001/002), cable list 860-001 | module lists and slots, terminals (-XX01..07), cables, supplies -> sheet 700, loop sheets, CAS-PID-900/901 |
| Design documents | `...\CAS - Automation and IT - CAS Styresystem - General design`: FD P-15169-CAS-FD-01 (newest rev), alarm list FD-02, Framo spec, Linde flowsheet, Servi hydraulics, action lists | equipment, tags, loops, interlocks, alarms -> sheets 100-600, CAS-PID-950 |
| Simulators | `C:\GIT\heimdall-cas-simulation` (scaleaq) | ports and register maps in the notes and on sheet 700 |

## Procedure

1. Note what changed since the revision in `\pidrev`. For each git source: `git log` since the last check.
   For each OneDrive folder: files newer than the last check (Get-ChildItem, LastWriteTime). Only re-read
   what changed.
2. PLC: re-extract the I/O mapping and the controller settings; diff against CAS-PID-900/901 and the notes
   on sheets 100-500. Update word numbers, variable names, ranges, setpoints and interlocks.
3. Drawings / cable list: new revisions? Diff module lists, terminals and cables against sheet 700, the loop
   sheets and CAS-PID-900/901.
4. FD and other documents: new revisions? Diff tags, loops, interlocks and alarms against sheets 100-600.
5. Update the sheets. Re-evaluate every open point on CAS-PID-950: resolved (delete it, and mention it in the
   revision note), still open, or changed. New findings get the next free id in their class.
6. Raise `\pidrev` (letter / date), build twice, look at every changed sheet as a rendered image
   (`pdftoppm -png -r 80`), fix overlaps.
7. Report: what changed, open points resolved / added, and which sources were not reachable.

## Revision history

| Rev | Date | Change |
|---|---|---|
| A | 2026-10-16 | First issue. PLC branch inletControl; drawings 792.001 rev 1, 792.002 rev 0; FD rev B. |
| B | 2026-10-16 | Cosmetic: pump and check valve symbols, Linde PV1--3 as control valves, no overlapping line markings, network sheet renamed CAS-LAY-700. A1 resolved: PLC CommonRIO reads 45 words, DI at word 44 (simulator 2.3.14, heimdall-cas-simulation #11). |
