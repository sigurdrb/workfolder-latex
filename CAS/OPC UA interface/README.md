# CAS PLC OPC UA interface reference

Generates the Confluence page that lists every node of GVLMain, the only node structure the CAS
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

Only GVLMain is documented (`--gvl` to change); other GVLs still ticked in the Symbol Configuration
are named in the output so they can be removed from the OPC server. The script also prints notes that no longer match a member (renamed or removed in the PLC) and types it
cannot find (library types). Update `notes.json` when a PLC change alters a node's behaviour.

## Put it in Confluence

Open the page, Edit, select all and delete, then `Insert` > `Markup` (or type `/markup`), choose
**Confluence wiki**, paste the content of `CAS OPC UA interface.confluence.txt`, Insert, Publish.
The `{anchor}` macros make the type links jump to the structure on the same page.

Deviations found while writing the notes go into `../Outstanding items.xlsx` (GEN-12, GEN-13).
