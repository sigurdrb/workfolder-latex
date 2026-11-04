# CAS PLC OPC UA interface reference

Generates the Confluence page that lists every node of GVLMain (GVLIO until 2026-11), the node structures the CAS
(Heimdall) PLC exposes over OPC UA: data type, what a client may do with it, and what it does (conditions, inhibits,
request/response). Structures and enumerations are linked.

| File | What |
|---|---|
| `gen_opc_interface.py` | Generator. Reads the CODESYS Git export of `scaleaq/heimdall-plc` (Symbol Configuration, DUTs, ENUMs, GVL_CONSTANT). |
| `notes.json` | Hand-maintained behaviour notes, keyed `<DUT>.<Member>` (also `GVLMain.<var>`, `ModbusRTUData.<var>`, `<ENUM>.<value>`), plus `_general` and `_structs`. |
| `CAS OPC UA interface.confluence.txt` | Output: Confluence wiki markup. |
| `CAS OPC UA interface.html` | Output: the same page for review in a browser. |

## Regenerate

```bash
git clone --depth 1 -b inletControl https://github.com/scaleaq/heimdall-plc.git /tmp/hplc
py gen_opc_interface.py /tmp/hplc
```

GVLMain is documented (`--gvl` to change; the RIO status of GVLIO moved into it in 2026-11); other GVLs ticked in the Symbol Configuration
are named in the output so they can be removed from the OPC server. The script also prints notes that no longer match a member (renamed or removed in the PLC) and types it
cannot find (library types). Update `notes.json` when a PLC change alters a node's behaviour.

## Put it in Confluence

Open the page, Edit, select all and delete, then `Insert` > `Markup` (or type `/markup`), choose
**Confluence wiki**, paste the content of `CAS OPC UA interface.confluence.txt`, Insert, Publish.
The `{anchor}` macros make the type links jump to the structure on the same page.

Deviations found while writing the notes go into `../Outstanding items.xlsx` (GEN-12, GEN-13).

## Commissioning use cases

`commissioning_usecases.py` writes `CAS commissioning use cases.confluence.txt` / `.html`: use cases
for field test and commissioning (structure after J. Cooling, *Software Engineering for Real-Time
Systems*, 2020, sec. 3.4.5), with the OPC UA nodes to write and read in order, the expected PLC
response and the error scenarios. Every node in it is checked against GVLMain (`opc_paths.py`); the
script fails and lists the references that do not exist, so a PLC rename shows up at once.

```bash
py commissioning_usecases.py /tmp/hplc
```
