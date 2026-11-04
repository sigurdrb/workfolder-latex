"""All GVLMain node paths of the CAS PLC, for checking documents that refer to OPC UA nodes.

    py opc_paths.py <heimdall-plc checkout> [--dump]

paths(repo) returns {path: type} with array indices written as [i] (e.g. "Inlet[i].InletPump.Command.Reset").
normalise(path) turns any index ([0], [2], [n]) into [i], so a document may use concrete indices.
"""
from __future__ import annotations

import re
import sys
from typing import Dict

import gen_opc_interface as g


def paths(repo: str, app: str = "pfc200_sim", gvl: str = "GVLMain") -> Dict[str, str]:
    structs, enums, consts, roots, _ = g.read_project(repo, app)
    out: Dict[str, str] = {}

    def walk(prefix: str, t: str, depth: int) -> None:
        dims, inner = g.array_info(t, consts)
        b = g.base_type(inner)
        p = prefix + ("[i]" * (dims.count(",") + 1) if dims else "")
        out[p] = t
        if b in structs and depth < 12:
            s = structs[b]
            members = list(s.members)
            if s.extends and s.extends in structs:
                members = structs[s.extends].members + members
            for m in members:
                walk(f"{p}.{m.name}", m.type, depth + 1)

    for r in roots:
        if r.gvl == gvl:
            walk(r.name, r.type, 0)
    return out


def normalise(path: str) -> str:
    path = path.strip()
    if path.startswith("GVLMain."):
        path = path[len("GVLMain."):]
    return re.sub(r"\[[^\]]*\]", "[i]", path)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    p = paths(sys.argv[1])
    if "--dump" in sys.argv:
        for k, v in p.items():
            print(f"{k}\t{v}")
    else:
        print(len(p), "paths")
