"""Generate the CAS PLC OPC UA interface reference (Confluence page) from the CODESYS project.

    py gen_opc_interface.py <heimdall-plc checkout> [--app pfc200_sim]

Reads the CODESYS Git export of scaleaq/heimdall-plc: the application's Symbol Configuration (which
GVLs and variables the OPC UA server publishes, and with which access), every DUT and ENUM, and
GVL_CONSTANT for array bounds. The behaviour of each node comes from notes.json next to this script
(hand-maintained, keyed "<DUT>.<Member>"); the declaration comments are the fallback.

Writes next to this script:
    CAS OPC UA interface.confluence.txt   Confluence wiki markup: in the editor, Insert > Markup >
                                          "Confluence wiki", paste, Insert (replaces the page body)
    CAS OPC UA interface.html             the same content for review in a browser
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_WIKI = os.path.join(HERE, "CAS OPC UA interface.confluence.txt")
OUT_HTML = os.path.join(HERE, "CAS OPC UA interface.html")
NOTES = os.path.join(HERE, "notes.json")

ELEMENTARY = {
    "BOOL", "BYTE", "WORD", "DWORD", "LWORD", "SINT", "USINT", "INT", "UINT", "DINT", "UDINT", "LINT",
    "ULINT", "REAL", "LREAL", "TIME", "LTIME", "DATE", "TOD", "DT", "TIME_OF_DAY", "DATE_AND_TIME",
    "STRING", "WSTRING",
}
ACCESS = {1: "read", 2: "write", 3: "read/write"}
ROLE_TEXT = {
    "write": "Command (client writes)",
    "config": "Setting (client may change)",
    "read": "Read",
    "internal": "PLC internal (do not write)",
}


# ------------------------------------------------------------------------------------------- export
def blobs(node):
    if isinstance(node, dict):
        for k, v in node.items():
            if k == "TextBlobForSerialisation" and isinstance(v, str):
                yield v[8:] if v.startswith("(string)") else v
            else:
                yield from blobs(v)
    elif isinstance(node, list):
        for v in node:
            yield from blobs(v)


def load_objects(root: str):
    """Yield (name, folder, data, texts) for every .object file below root."""
    for d, _, files in os.walk(root):
        for f in files:
            if f.endswith(".object"):
                p = os.path.join(d, f)
                data = json.load(open(p, encoding="utf-8-sig"))
                name = data["payload"]["meta"]["Graph"]["@Value"]["Name"]
                name = name[8:] if name.startswith("(string)") else name
                yield name, os.path.relpath(d, root).replace("\\", "/"), data, list(blobs(data))


# ------------------------------------------------------------------------------------------- types
@dataclass
class Member:
    name: str
    type: str
    default: str = ""
    comment: str = ""
    group: str = ""          # the // comment line(s) just above, if any


@dataclass
class Struct:
    name: str
    folder: str
    comment: str = ""
    extends: str = ""
    members: List[Member] = field(default_factory=list)


@dataclass
class Enum:
    name: str
    comment: str = ""
    base: str = "INT"
    values: List[Tuple[str, Optional[int], str]] = field(default_factory=list)


def strip_attrs(text: str) -> str:
    return re.sub(r"\{attribute[^}]*\}", "", text)


def split_code_comment(line: str) -> Tuple[str, str]:
    m = re.search(r"//", line)
    if not m:
        line2 = re.sub(r"\(\*.*?\*\)", "", line)
        cm = re.findall(r"\(\*(.*?)\*\)", line)
        return line2, " ".join(c.strip() for c in cm)
    return line[:m.start()], line[m.end():].strip()


def parse_struct(name: str, folder: str, text: str) -> Struct:
    text = strip_attrs(text)
    s = Struct(name, folder)
    head, _, body = text.partition("STRUCT")
    m = re.search(r"EXTENDS\s+(\w+)", head)
    if m:
        s.extends = m.group(1)
    s.comment = " ".join(split_code_comment(l)[1] for l in head.splitlines() if "//" in l).strip()
    body = body.split("END_STRUCT")[0]
    group: List[str] = []
    last: Optional[Member] = None
    for raw in body.splitlines():
        code, comment = split_code_comment(raw)
        code = code.strip()
        if not code:
            if comment and last is not None and raw.startswith(("\t\t\t", "        ")) and not group:
                last.comment = (last.comment + " " + comment).strip()      # continued comment
            elif comment:
                group.append(comment)
            else:
                group = []
            continue
        m = re.match(r"([\w\s,]+?)\s*:\s*(.+?)\s*(?::=\s*(.+?))?\s*;\s*$", code)
        if not m:
            continue
        names = [n.strip() for n in m.group(1).split(",")]
        for n in names:
            last = Member(n, re.sub(r"\s+", " ", m.group(2)), (m.group(3) or "").strip(), comment, " ".join(group))
            s.members.append(last)
        group = []
    return s


def parse_enum(name: str, text: str) -> Enum:
    text = strip_attrs(text)
    e = Enum(name)
    head, _, rest = text.partition("(")
    e.comment = " ".join(split_code_comment(l)[1] for l in head.splitlines() if "//" in l).strip()
    body, _, tail = rest.rpartition(")")
    m = re.match(r"\s*(\w+)", tail)
    if m and m.group(1) != "END_TYPE":
        e.base = m.group(1)
    nxt = 0
    for raw in body.splitlines():
        code, comment = split_code_comment(raw)
        for part in [p for p in code.split(",") if p.strip()]:
            m = re.match(r"\s*(\w+)\s*(?::=\s*(-?\w+))?", part)
            if not m:
                continue
            val = nxt
            if m.group(2) is not None:
                try:
                    val = int(m.group(2), 0)
                except ValueError:
                    val = None
            e.values.append((m.group(1), val, comment))
            nxt = (val or 0) + 1
    return e


def array_info(t: str, consts: Dict[str, int]) -> Tuple[str, str]:
    """('ARRAY[0..2] OF InletDUT') -> ('[0..2]', 'InletDUT'); plain types -> ('', type)."""
    m = re.match(r"ARRAY\s*\[(.+?)\]\s*OF\s+(.+)", t, re.I)
    if not m:
        return "", t

    def ev(x: str) -> str:
        x = x.strip()
        for k, v in consts.items():
            x = re.sub(r"(?:GVL_CONSTANT\.)?\b" + re.escape(k) + r"\b", str(v), x, flags=re.I)
        x = x.replace("(", "").replace(")", "")
        try:
            return str(eval(x, {"__builtins__": {}}))   # noqa: S307 - small integer arithmetic from the project
        except Exception:                                # noqa: BLE001
            return x

    dims = []
    for dim in m.group(1).split(","):
        lo, _, hi = dim.partition("..")
        dims.append(f"{ev(lo)}..{ev(hi)}")
    return "[" + ",".join(dims) + "]", m.group(2).strip()


def base_type(t: str) -> str:
    t = re.sub(r"\(.*\)", "", t).strip()     # STRING(255)
    return t.upper() if t.upper() in ELEMENTARY else t


# ------------------------------------------------------------------------------------------- model
@dataclass
class Root:
    gvl: str
    name: str
    type: str
    access: int


def read_project(repo: str, app: str):
    proj = os.path.join(repo, "project")
    structs: Dict[str, Struct] = {}
    enums: Dict[str, Enum] = {}
    consts: Dict[str, int] = {}
    roots: List[Root] = []
    gvl_decl: Dict[str, str] = {}
    fbs: Dict[str, Tuple[str, str]] = {}
    for name, folder, data, texts in load_objects(proj):
        top = folder.split("/")[0]
        if top.startswith(("controlwinsim", "siteprogram", "simulation")):
            continue
        if top.startswith(("pfc200", "pfc")) and not top.startswith(app):
            continue
        for t in texts:
            ts = strip_attrs(t).lstrip()
            if ts.startswith("TYPE") or re.match(r"(//.*\n\s*)*TYPE", ts):
                if "STRUCT" in ts:
                    structs[name] = parse_struct(name, folder, t)
                elif re.search(r"TYPE\s+\w+\s*:\s*(//.*\n\s*)*\(", ts, re.S):
                    enums[name] = parse_enum(name, t)
            elif ts.startswith("FUNCTION_BLOCK"):
                fbs[name] = (folder, t)
            elif re.match(r"(//.*\n\s*)*VAR_GLOBAL", ts):
                gvl_decl[name] = t
                if name == "GVL_CONSTANT":
                    for m in re.finditer(r"(\w+)\s*:\s*\w+\s*:=\s*(\d+)\s*;", t):
                        consts[m.group(1)] = int(m.group(2))
        if folder.split("/")[-1].startswith("symbols_") and top.startswith(app):
            graph = data["payload"]["object"]["Graph"]["@Value"]
            for sign in graph["SelectionSigns"]["@Value"]:
                sv = sign["@Value"]
                gvl = sv["SignName"][8:]
                for var in sv["SignVariables"]["@Value"]:
                    vv = var["@Value"]
                    roots.append(Root(gvl, vv["VarName"][8:], vv["VarType"][8:], int(vv["VarAccess"][5:])))
    # The Symbol Configuration keeps variables removed from the GVL until it is built again: leave them out.
    declared = {g: set(re.findall(r"^\s*(\w+)\s*:", strip_attrs(t), re.M)) for g, t in gvl_decl.items()}
    stale = [r for r in roots if r.gvl in declared and r.name not in declared[r.gvl]]
    for r in stale:
        print(f"Symbol Configuration lists {r.gvl}.{r.name}, which the GVL no longer declares: left out",
              file=sys.stderr)
    roots = [r for r in roots if r not in stale]
    # A published function block instance: its own variables are nodes. Library internals are left out.
    for r in roots:
        t = base_type(array_info(r.type, consts)[1])
        if t in fbs and t not in structs:
            structs[t] = parse_fb(t, *fbs[t])
    return structs, enums, consts, roots, gvl_decl


FB_SKIP = re.compile(r"^(TON|TOF|TP|R_TRIG|F_TRIG|typMb\w*|\w+\.\w+)$", re.I)


def parse_fb(name: str, folder: str, text: str) -> Struct:
    """Variables of a function block (VAR_INPUT, VAR_OUTPUT, VAR) as a Struct; VAR_IN_OUT are references."""
    text = strip_attrs(text)
    s = Struct(name, folder)
    s.comment = " ".join(split_code_comment(l)[1] for l in text.split("VAR")[0].splitlines()
                         if "//" in l).strip()
    s.comment = (s.comment + " Function block instance: its variables are published; library blocks "
                 "inside it are not listed.").strip()
    for sec in re.finditer(r"\bVAR(_INPUT|_OUTPUT)?\b(?!_IN_OUT)(.*?)\bEND_VAR", text, re.S):
        if sec.group(0).startswith("VAR_IN_OUT"):
            continue
        part = parse_struct(name, folder, "STRUCT\n" + sec.group(2) + "\nEND_STRUCT")
        s.members += [m for m in part.members if not FB_SKIP.match(base_type(array_info(m.type, {})[1]))]
    return s


def reachable(roots: List[Root], structs, enums, consts) -> Tuple[List[str], List[str]]:
    order: List[str] = []
    seen = set()
    enum_order: List[str] = []

    def visit(t: str):
        _, t = array_info(t, consts)
        t = base_type(t)
        if t in enums and t not in enum_order:
            enum_order.append(t)
        if t not in structs or t in seen:
            return
        seen.add(t)
        order.append(t)
        s = structs[t]
        if s.extends:
            visit(s.extends)
        for m in s.members:
            visit(m.type)

    for r in roots:
        visit(r.type)
    return order, enum_order


# ------------------------------------------------------------------------------------------- notes
def role_of(dut: str, member: str, mtype: str, note: dict, structs) -> str:
    if note.get("client"):
        return note["client"]
    if "InternalCommand" in dut:
        return "internal"
    if "AlarmAck" in dut:
        return "write"
    if "Command" in dut:
        return "write"
    if "Config" in dut or dut == "PenConfigDUT":
        return "config"
    return "read"


def describe(dut: str, m: Member, notes: dict) -> Tuple[str, str, str]:
    n = notes.get(f"{dut}.{m.name}", {})
    desc = n.get("desc") or m.comment or ""
    if not n.get("desc") and m.group and not m.comment:
        desc = m.group
    beh = n.get("behaviour", "")
    unit = n.get("unit", "")
    return desc, beh, unit


# ------------------------------------------------------------------------------------------- render
WIKI_ESC = re.compile(r"([\\|\[\]{}*_+^~#-])")


def w(text: str) -> str:
    """Escape free text for Confluence wiki markup (table cells and paragraphs)."""
    text = (text or "").replace("\r", " ").replace("\n", " ")
    return WIKI_ESC.sub(r"\\\1", text)


def anchor(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", name)


def type_wiki(t: str, structs, enums, consts) -> str:
    dims, inner = array_info(t, consts)
    b = base_type(inner)
    shown = w(inner)
    if b in structs or b in enums:
        shown = f"[{b}|#{anchor(b)}]"
    elif b not in ELEMENTARY:
        shown += " (library type)"
    return (f"ARRAY{w(dims)} OF " if dims else "") + shown


def type_html(t: str, structs, enums, consts) -> str:
    dims, inner = array_info(t, consts)
    b = base_type(inner)
    shown = html.escape(inner)
    if b in structs or b in enums:
        shown = f'<a href="#{anchor(b)}">{html.escape(b)}</a>'
    elif b not in ELEMENTARY:
        shown += " (library type)"
    return (f"ARRAY{html.escape(dims)} OF " if dims else "") + shown


INTRO = [
    ("What this page is",
     "The variables the CAS (Heimdall) PLC publishes on its OPC UA server: every node, its data type, "
     "and what it does when you read or write it. It is generated from the CODESYS project "
     "(scaleaq/heimdall-plc) and the notes in workfolder-latex/CAS/OPC UA interface, so it follows the "
     "program. Do not edit the page by hand: change notes.json or the PLC and regenerate."),
    ("Address space",
     "The server publishes the application's Symbol Configuration. Node ids are CODESYS string ids, "
     "ns=4;s=|var|<device>.Application.<GVL>.<path>, e.g. ...Application.GVLMain.Inlet[0].InletPump.Command.Reset. "
     "Device name and namespace index differ between PLCs: find GVLMain by browsing once per session. "
     "Clients use GVLMain (plant, commands, settings, and since 2026-11 the remote I/O link status and alarms "
     "that were in GVLIO: InletRIO[i], CommonRIO). It is exported whole, so every member below is a node. The real PLC needs a user login (no anonymous access)."),
    ("Structure of a device",
     "Most devices use the same sub-structures: Command (client writes: requests and setpoints), "
     "Status (PLC result: state, mode, permits), Input (measured values, after scaling), Output "
     "(what the PLC drives), Alarm (one AlarmState per alarm), AlarmAck (client writes to acknowledge), "
     "Config (settings; many are retained) and InternalCommand (between PLC blocks: never write). "
     "The column 'Client' says what a client may do with a node."),
    ("Commands",
     "Commands are pulses unless stated otherwise: write TRUE, hold at least 1 s or until the PLC clears it, "
     "then write FALSE. Mode commands (Manual / Auto) are cleared by the PLC. A command the PLC cannot accept "
     "is ignored or reported (e.g. Pen.Status.CommandRejected); check the Status member named in the "
     "behaviour column for the result. Write only Command members, AlarmAck bits and the named settings; "
     "never Status, Input, Output, Alarm or InternalCommand."),
    ("Alarms",
     "Each alarm is an AlarmState (0 Normal, 1 Unacknowledged, 2 Acknowledged, 3 RetainUnacknowledged, "
     "4 Suppressed). Acknowledge with a rising edge on the matching AlarmAck bit."),
    ("Client rules",
     "Clients must follow 'CAS requirements for OPC UA clients of the PLC' (workfolder-latex/CAS): one "
     "session, subscriptions instead of polling (>= 1 s), reconnect with back-off, show values as unknown "
     "while the link is down, respect quality flags (BadQuality, CommOK)."),
]


def render(structs, enums, consts, roots, order, enum_order, notes, source: str):
    general = notes.get("_general", {})
    sdesc = notes.get("_structs", {})
    today = dt.date.today().isoformat()
    W: List[str] = []
    H: List[str] = []

    W.append("{info}Generated " + today + " from " + w(source) + ". Do not edit here: change the PLC or "
             "notes.json in workfolder-latex/CAS/OPC UA interface and regenerate.{info}")
    W.append("{toc:maxLevel=2}")
    H.append(f"<p class='gen'>Generated {today} from {html.escape(source)}.</p>")

    W.append("h1. How to use this page")
    H.append("<h1>How to use this page</h1>")
    for title, text in INTRO:
        extra = {"Commands": "commands", "Alarms": "alarm_ack", "Structure of a device": "status"}.get(title)
        if extra and general.get(extra):
            text = text + " " + general[extra]
        W.append(f"*{w(title)}.* {w(text)}")
        H.append(f"<p><b>{html.escape(title)}.</b> {html.escape(text)}</p>")
    for key in ("config", "internal"):
        if general.get(key):
            W.append(f"*{key.capitalize()}.* {w(general[key])}")
            H.append(f"<p><b>{key.capitalize()}.</b> {html.escape(general[key])}</p>")

    # roots
    W.append("h1. Root nodes")
    H.append("<h1>Root nodes</h1>")
    W.append("|| GVL || Node || Type || Access || Description ||")
    H.append("<table><tr><th>GVL</th><th>Node</th><th>Type</th><th>Access</th><th>Description</th></tr>")
    for r in roots:
        n = notes.get(f"{r.gvl}.{r.name}", {})
        desc = " ".join(x for x in (n.get("desc", ""), n.get("behaviour", "")) if x) \
            or sdesc.get(base_type(array_info(r.type, consts)[1]), "")
        W.append(f"| {w(r.gvl)} | *{w(r.name)}* | {type_wiki(r.type, structs, enums, consts)} | "
                 f"{ACCESS.get(r.access, r.access)} | {w(desc)} |")
        H.append(f"<tr><td>{r.gvl}</td><td><b>{html.escape(r.name)}</b></td>"
                 f"<td>{type_html(r.type, structs, enums, consts)}</td><td>{ACCESS.get(r.access, r.access)}</td>"
                 f"<td>{html.escape(desc)}</td></tr>")
    H.append("</table>")

    # structures
    W.append("h1. Structures")
    H.append("<h1>Structures</h1>")
    for name in order:
        s = structs[name]
        desc = sdesc.get(name) or s.comment
        W.append(f"h2. {{anchor:{anchor(name)}}}{name}")
        H.append(f"<h2 id='{anchor(name)}'>{html.escape(name)}</h2>")
        if desc:
            W.append(w(desc))
            H.append(f"<p>{html.escape(desc)}</p>")
        if s.extends:
            W.append(f"Extends [{s.extends}|#{anchor(s.extends)}] (its members come first).")
            H.append(f"<p>Extends <a href='#{anchor(s.extends)}'>{s.extends}</a>.</p>")
        if not s.members:
            W.append("_No members (placeholder)._")
            H.append("<p><i>No members (placeholder).</i></p>")
            continue
        W.append("|| Member || Type || Client || Description || Behaviour, conditions ||")
        H.append("<table><tr><th>Member</th><th>Type</th><th>Client</th><th>Description</th>"
                 "<th>Behaviour, conditions</th></tr>")
        for m in s.members:
            note = notes.get(f"{name}.{m.name}", {})
            role = role_of(name, m.name, m.type, note, structs)
            desc, beh, unit = describe(name, m, notes)
            if unit:
                desc = f"{desc} [{unit}]" if desc else f"[{unit}]"
            if m.default:
                beh = (beh + " " if beh else "") + f"Default {m.default}."
            dims, inner = array_info(m.type, consts)
            is_struct = base_type(inner) in structs
            role_txt = "" if is_struct else ROLE_TEXT.get(role, role)
            W.append(f"| *{w(m.name)}* | {type_wiki(m.type, structs, enums, consts)} | {w(role_txt)} | "
                     f"{w(desc)} | {w(beh)} |")
            H.append(f"<tr class='{role}'><td><b>{html.escape(m.name)}</b></td>"
                     f"<td>{type_html(m.type, structs, enums, consts)}</td><td>{html.escape(role_txt)}</td>"
                     f"<td>{html.escape(desc)}</td><td>{html.escape(beh)}</td></tr>")
        H.append("</table>")

    # enums
    W.append("h1. Enumerations")
    H.append("<h1>Enumerations</h1>")
    for name in enum_order:
        e = enums[name]
        W.append(f"h2. {{anchor:{anchor(name)}}}{name}")
        H.append(f"<h2 id='{anchor(name)}'>{html.escape(name)}</h2>")
        desc = sdesc.get(name) or e.comment
        if desc:
            W.append(w(desc) + f" Base type {e.base}.")
            H.append(f"<p>{html.escape(desc)} Base type {e.base}.</p>")
        W.append("|| Value || Name || Meaning ||")
        H.append("<table><tr><th>Value</th><th>Name</th><th>Meaning</th></tr>")
        for vname, val, comment in e.values:
            meaning = notes.get(f"{name}.{vname}", {}).get("desc") or comment
            W.append(f"| {'' if val is None else val} | *{w(vname)}* | {w(meaning)} |")
            H.append(f"<tr><td>{'' if val is None else val}</td><td><b>{html.escape(vname)}</b></td>"
                     f"<td>{html.escape(meaning)}</td></tr>")
        H.append("</table>")

    css = ("body{font-family:system-ui,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;"
           "color:#1f2328;background:#fff}table{border-collapse:collapse;width:100%;margin:8px 0 20px}"
           "th,td{border:1px solid #d0d7de;padding:4px 8px;vertical-align:top;font-size:13px;text-align:left}"
           "th{background:#f6f8fa}tr.write td:nth-child(3){color:#0969da;font-weight:600}"
           "tr.config td:nth-child(3){color:#9a6700}tr.internal td:nth-child(3){color:#cf222e}"
           ".gen{color:#57606a}h2{border-top:1px solid #d0d7de;padding-top:12px}")
    page = ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>CAS OPC UA interface</title>"
            f"<style>{css}</style></head><body><h1>CAS (Heimdall) PLC: OPC UA interface</h1>"
            + "\n".join(H) + "</body></html>")
    return "\n".join(W) + "\n", page


# ------------------------------------------------------------------------------------------- main
def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("repo", help="checkout of scaleaq/heimdall-plc")
    ap.add_argument("--app", default="pfc200_sim", help="application folder prefix (default pfc200_sim)")
    ap.add_argument("--gvl", default=["GVLMain"], nargs="+",
                    help="published GVLs to document (default GVLMain; GVLIO is gone since 2026-11)")
    args = ap.parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")

    structs, enums, consts, roots, _ = read_project(args.repo, args.app)
    if not roots:
        print("No Symbol Configuration found for", args.app, file=sys.stderr)
        return 1
    others = sorted({r.gvl for r in roots if r.gvl not in args.gvl})
    roots = [r for r in roots if r.gvl in args.gvl]
    if others:
        print("Also published in the Symbol Configuration, left out of the page:", ", ".join(others))
    order, enum_order = reachable(roots, structs, enums, consts)
    notes = json.load(open(NOTES, encoding="utf-8")) if os.path.exists(NOTES) else {}
    try:
        rev = subprocess.run(["git", "-C", args.repo, "log", "-1", "--format=%h %cs %D"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except Exception:                       # noqa: BLE001
        rev = "unknown revision"
    source = f"scaleaq/heimdall-plc {rev}, application {args.app}"
    wiki, page = render(structs, enums, consts, roots, order, enum_order, notes, source)
    open(OUT_WIKI, "w", encoding="utf-8").write(wiki)
    open(OUT_HTML, "w", encoding="utf-8").write(page)

    keys = {f"{n}.{m.name}" for n in order for m in structs[n].members}
    keys |= {f"{r.gvl}.{r.name}" for r in roots}
    unused = sorted(k for k in notes if not k.startswith("_") and k not in keys
                    and k.split(".")[0] in set(order) | {"GVLMain"})
    missing_types = sorted({base_type(array_info(m.type, consts)[1]) for n in order for m in structs[n].members}
                           - set(structs) - set(enums) - ELEMENTARY)
    print(f"{len(roots)} root nodes, {len(order)} structures, {len(enum_order)} enumerations, "
          f"{sum(len(structs[n].members) for n in order)} members")
    if missing_types:
        print("Types not found in the project:", ", ".join(missing_types))
    if unused:
        print(f"{len(unused)} notes do not match a member (renamed or removed):", ", ".join(unused[:20]))
    print("Wrote", OUT_WIKI, "and", OUT_HTML)
    return 0


if __name__ == "__main__":
    sys.exit(main())
