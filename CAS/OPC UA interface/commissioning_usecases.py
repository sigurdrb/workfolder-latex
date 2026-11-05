"""CAS commissioning: one card per system with its settings, commands and status nodes.

    py commissioning_usecases.py <heimdall-plc checkout>

For each system: which top-level branches of GVLMain to open, the settings (Config), commands and status nodes in
one table, and a short start-and-verify sequence. Ends with suggestions for moving nodes so that one system needs
fewer branches. Every node written in backticks, and every node in the tables, is checked against the PLC project
(opc_paths.py); the script lists the references that do not exist and exits with 1.

Writes next to this script:
    CAS commissioning use cases.confluence.txt   Confluence wiki markup (Insert > Markup > Confluence wiki)
    CAS commissioning use cases.html             the same for review in a browser
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import subprocess
import sys

import opc_paths

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_WIKI = os.path.join(HERE, "CAS commissioning use cases.confluence.txt")
OUT_HTML = os.path.join(HERE, "CAS commissioning use cases.html")

INTRO = (
    "One card per system: the top-level branches of GVLMain to open, the settings, commands and status nodes in one "
    "table, and a short sequence to start and verify the system. Paths are relative to GVLMain and checked against the "
    "PLC program; [i] is 0-based (Inlet[0] = inlet 1). Every node's type and behaviour: page 'CAS OPC UA interface'.")

CONVENTIONS = [
    ("Pulse", "Write TRUE; the PLC clears it. All Manual / Auto, `Pen.Command.Start` / Stop / OxygenStart / "
              "OxygenStop, `Inlet[i].InletPump.Command.Reset` (cleared when the pump state changes), calibrations, "
              "`Outlet.Command.FaultReset`."),
    ("Held", "Write TRUE; the PLC holds it until the state confirms, then clears it: InletPump, OxyPump and "
             "HydraulicPump Start / Stop (in manual)."),
    ("Edge", "Write TRUE, then FALSE yourself: `OxySystem[i].OxyPump.Command.Reset`, every AlarmAck bit."),
    ("Value", "Setpoints and modes: write the value, it stays (Setpoint, ManualOutput, ManualPosition, Mode)."),
    ("Setting", "Config members: retained over a restart (GVLRetain). Change only during commissioning."),
]

# id, name, what, branches, settings, commands, status, steps, alarms
SYSTEMS = []


def system(**k):
    SYSTEMS.append(k)


system(
    id="S1", name="Field links: remote I/O, drives, Framo",
    what="Modbus TCP to CommonRIO and InletRIO 1..3 (Wago 750-362), the oxy pump drives (ATV650) behind each "
         "InletRIO, and OPC UA to the Framo pump controllers (PCC 1..3). Check these first.",
    branches=["CommonRIO", "InletRIO[i]", "Inlet[i]", "OxySystem[i]"],
    settings=[("CommonRIO.Config.IP", "IP and Port of the common coupler"),
              ("InletRIO[i].Config.IP", "coupler of inlet station i, with Port"),
              ("InletRIO[i].Config.DriveIP", "oxy pump drive, with DrivePort, DriveUnitId, DriveEnabled"),
              ("Inlet[i].Config.FramoIP", "Framo PCC i, with FramoPort, FramoUpdateRate")],
    commands=[],
    status=[("CommonRIO.Status.CommOK", "link up and data fresh"),
            ("InletRIO[i].Status.CommOK", "same per inlet station; DataStale = answers but no new data"),
            ("OxySystem[i].OxyPump.Status.CommunicationOK", "drive link"),
            ("Inlet[i].InletPump.Status.FramoConnected", "OPC UA data source connected"),
            ("Inlet[i].InletPump.Status.CommunicationOK", "Framo heartbeat answered"),
            ("InletRIO[i].Status.Restarts", "link restarts; also DriveRestarts, CommonRIO.Status.Restarts, "
                                            "Inlet[i].InletPump.Status.FramoRestarts"),
            ("InletRIO[i].Status.Watchdog", "coupler Modbus watchdog: State, Expiries")],
    steps=["Check the IP settings; 0.0.0.0 means not configured (`InletRIO[i].Status.MissingIP`).",
           "All CommOK / CommunicationOK / FramoConnected TRUE.",
           "Over a few minutes: the restart counters do not count and `InletRIO[i].Status.DataStale` stays FALSE."],
    alarms=["CommonRIO.Alarm", "InletRIO[i].Alarm"])

system(
    id="S2", name="Instruments",
    what="Every measurement is an AnalogSensor (or DigitalSensor): .Filtered is the value in engineering units, "
         ".ScaledRaw the unfiltered value, .Status.BadQuality the quality, .Config the range and filter.",
    branches=["Pen", "Inlet[i]", "OxySystem[i]"],
    settings=[("Inlet[i].Input.LevelInsidePen.Config", "range, filter, alarm limits (same layout for every sensor)")],
    commands=[],
    status=[("Inlet[i].Input.LevelInsidePen.Filtered", "level transmitters per inlet, also LevelOutsidePen, "
                                                       "PenOverHeight"),
            ("Pen.Input.AverageLevelInside.Filtered", "pen averages: AverageLevelOutside, AverageOverHeight"),
            ("Pen.Input.Orbit864Sensor[i].OxygenConcentration.Filtered", "O2 sensors; also OxygenSaturation, "
                                                                         "Temperature, Salinity"),
            ("Pen.Input.Orbit864Sensor[i].Status.CommOK", "Orbit 864 on Modbus RTU"),
            ("Pen.Input.AverageOxygenForControl.Filtered", "O2 used by OIC01"),
            ("OxySystem[i].Input.OxyPumpPressure.Filtered", "oxy line pressures: OxynatorOutletPressure, "
                                                            "OxyInjectionPressure"),
            ("OxySystem[i].Input.OxygenFlow.Filtered", "O2 flow per line"),
            ("Inlet[i].Input.LevelInsidePen.Status.BadQuality", "quality of any sensor")],
    steps=["Per transmitter: compare .Filtered with the local reading; .Status.BadQuality FALSE.",
           "Disconnect one transmitter: BadQuality TRUE, its pair leaves the pen average.",
           "O2 sensors: `Pen.Input.Orbit864Sensor[i].Status.CommOK` TRUE before reading values."],
    alarms=["Inlet[i].Input.LevelInsidePen.Alarm", "Pen.Input.Orbit864Sensor[i].Alarm"])

system(
    id="S3", name="Inlet pump i (Framo)",
    what="Framo pump controller PCC i over OPC UA. In auto the pen (S5) starts and stops it and sets its speed.",
    branches=["Inlet[i]"],
    settings=[("Inlet[i].Config.InletPumpEnable", "takes part in the automatic pump count"),
              ("Inlet[i].Config.StartupTime", "start / stop supervision, with ShutdownTime"),
              ("Inlet[i].Config.HeartbeatTimeout", "link supervision, with HeartbeatInterval"),
              ("Inlet[i].Config.SpeedDeviationLimit", "speed deviation alarm, with SpeedDeviationDelay"),
              ("Inlet[i].Config.ResetExpectedTime", "time for a Reset to change the pump state")],
    commands=[("Inlet[i].InletPump.Command.Manual", "pulse; Auto back"),
              ("Inlet[i].InletPump.Command.Setpoint", "manual speed, rpm 40..130"),
              ("Inlet[i].InletPump.Command.Start", "held, in manual; Stop the same"),
              ("Inlet[i].InletPump.Command.Reset", "pulse, after a trip (Hold / Lockdown)")],
    status=[("Inlet[i].InletPump.State", "Available 0, Starting 1, Remote 2 (running), Stopping 3, Hold 4, "
                                         "Lockdown 5, Unavailable 9"),
            ("Inlet[i].InletPump.Status.Manual", "mode"),
            ("Inlet[i].InletPump.Status.ActualSpeed", "rpm"),
            ("Inlet[i].InletPump.Status.CommunicationOK", "heartbeat AND FramoConnected"),
            ("Inlet[i].InletPump.Input.MotorCurrent", "also MotorPower, MotorTemperatureHH")],
    steps=["`Inlet[i].InletPump.Status.CommunicationOK` TRUE, State Available (0).",
           "Pulse Manual, write Setpoint 60, Start: State 1 then 2, ActualSpeed follows.",
           "Change Setpoint; Stop: State 3 then 0. Pulse Auto."],
    alarms=["Inlet[i].InletPump.Alarm"])

system(
    id="S4", name="Oxygen line i",
    what="Oxy pump (ATV650 drive) on the side stream, the O2 control valve and its pressure and flow control. In auto "
         "the line follows Pen OxygenStart / OxygenStop and OIC01 (S6).",
    branches=["OxySystem[i]"],
    settings=[("OxySystem[i].Config.Enable", "the line takes part in oxygenation"),
              ("OxySystem[i].Config.ValveOpenPressure", "the valve may open above this pump pressure"),
              ("OxySystem[i].Config.PressureSetpoint", "pressure control (PressureController)"),
              ("OxySystem[i].Config.FlowMax", "max O2 flow per line (FlowController)"),
              ("OxySystem[i].Config.OxyPump", "MinSpeed_Hz, MaxSpeed_Hz, PresetSpeed_Hz"),
              ("OxySystem[i].Config.OxyStartupTime", "with OxyShutdownTime, ValveRampTime")],
    commands=[("OxySystem[i].OxyPump.Command.Manual", "pulse; Auto back"),
              ("OxySystem[i].OxyPump.Command.Setpoint", "manual speed, Hz"),
              ("OxySystem[i].OxyPump.Command.Start", "held, in manual; Stop the same"),
              ("OxySystem[i].OxyPump.Command.Reset", "edge: drive fault reset"),
              ("OxySystem[i].OxyValve.Command.Manual", "pulse; Auto back"),
              ("OxySystem[i].OxyValve.Command.ManualSetpoint", "valve %, used while permitted")],
    status=[("OxySystem[i].Status.State", "Stopped 0, Starting 1, Running 2, Faulted 9"),
            ("OxySystem[i].Status.ValvePermit", "pump running and pressure above ValveOpenPressure"),
            ("OxySystem[i].Status.OxyFlow", "with FlowSetpoint, OxyValvePosition, OxyPumpSpeed"),
            ("OxySystem[i].OxyPump.State", "Available 0, Starting 1, Running 2, Stopping 3, Unavailable 4"),
            ("OxySystem[i].OxyPump.Status.AutoResets", "automatic drive resets after a link fault"),
            ("OxySystem[i].OxyPump.Input.LastFault", "drive fault code (LFT)"),
            ("OxySystem[i].Input.OxyPumpPressure.Filtered", "pump pressure")],
    steps=["Config.Enable TRUE; pulse OxyPump Manual, Setpoint 30, Start: OxyPump.State 2.",
           "OxyPumpPressure above ValveOpenPressure: Status.ValvePermit TRUE.",
           "Pulse OxyValve Manual, ManualSetpoint 20: OxyFlow rises. Then both back to Auto."],
    alarms=["OxySystem[i].Alarm", "OxySystem[i].OxyPump.Alarm"])

system(
    id="S5", name="Pen and level control (LIC01)",
    what="The pen sequence starts the inlet pumps in auto, shares the speed between them and keeps the level at the "
         "setpoint (LIC01). Needs S1 and S3 with the pumps in auto.",
    branches=["Pen", "LevelController", "PenInletSupervisor"],
    settings=[("Pen.Config.LevelController", "Kp, Ti, MinOutput, MaxOutput, SafeOutput"),
              ("Pen.Config.PumpAddSpeed", "pump count: PumpTargetSpeed, PumpAddDelay, PumpRemoveDelay"),
              ("Pen.Config.PumpCycleTime", "rotation"),
              ("Pen.Config.LevelDeviationLimit", "with LevelDeviationDelay")],
    commands=[("Pen.Command.LevelSetpoint", "value, m"),
              ("Pen.Command.Start", "pulse; Stop the same"),
              ("LevelController.Command.Manual", "pulse; Auto back"),
              ("LevelController.Command.ManualOutput", "rpm per pump, in manual")],
    status=[("Pen.Status.State", "Stopped 0, Starting 1, Running 2, Stopping 3"),
            ("Pen.Status.Ready", "start allowed; PumpReady: a pump can start"),
            ("Pen.Status.CommandRejected", "last command did not fit the state"),
            ("Pen.Status.OverHeight", "level inside minus outside"),
            ("LevelController.Input.ProcessValue", "with Setpoint, LimitsActive"),
            ("LevelController.Output.OUT", "speed share"),
            ("PenInletSupervisor.PumpsWanted", "with NumberOfInletsRunning, NumberOfInletsInAuto")],
    steps=["Pumps in auto with `Inlet[i].Config.InletPumpEnable`; `Pen.Status.Ready` TRUE.",
           "Write LevelSetpoint, pulse Start: State 1 then 2, pumps start one by one.",
           "ProcessValue settles at Setpoint; PumpsWanted follows the load. Stop: State 3 then 0."],
    alarms=["Pen.Alarm", "LevelController.Alarm"])

system(
    id="S6", name="Pen oxygen control (OIC01)",
    what="Controls the pen O2 to its setpoint by sharing the O2 flow over the lines in auto. Needs S2 (O2 sensors), "
         "S4 and the pen running (S5).",
    branches=["Pen", "OxyController", "OxySystem[i]"],
    settings=[("Pen.Config.OxySetpoint", "mg/L"),
              ("Pen.Config.OxyController", "Kp, Ti, MinOutput, MaxOutput"),
              ("Pen.Input.Orbit864Sensor[i].Config.EnableForAutoControl", "sensor used for the control value")],
    commands=[("Pen.Command.OxygenStart", "pulse; OxygenStop the same"),
              ("OxyController.Command.Manual", "pulse; Auto back"),
              ("OxyController.Command.ManualOutput", "total O2 flow kg/h, in manual")],
    status=[("Pen.Status.OxygenOn", "oxygenation started"),
            ("Pen.Status.OxyControlOK", "control value valid"),
            ("Pen.Input.AverageOxygenForControl.Filtered", "control value"),
            ("OxyController.Output.OUT", "total O2 flow"),
            ("OxySystem[i].Status.InAuto", "line follows OIC01; FlowSetpoint per line")],
    steps=["Pen running, lines with Config.Enable and pump and valve in auto.",
           "Pulse OxygenStart: OxygenOn TRUE, lines Running (`OxySystem[i].Status.State` 2).",
           "AverageOxygenForControl moves toward OxySetpoint; OxygenStop closes the valves."],
    alarms=["OxyController.Alarm"])

system(
    id="S7", name="Outlet (dampers and hydraulics)",
    what="Four cylinders open the outlet to a position per operation mode, driven by the hydraulic pump.",
    branches=["Outlet"],
    settings=[("Outlet.Config.ModePosition", "opening per mode O35, O45, O60, S75 (%)"),
              ("Outlet.Config.MaxTravelTimeOpen", "with MaxTravelTimeClose, RampRateOpen, RampRateClose"),
              ("Outlet.Cylinder[i].Config.OpenPosition", "calibration counts, with ClosedPosition")],
    commands=[("Outlet.Command.Mode", "value: O35 0, O45 1, O60 2, S75 3"),
              ("Outlet.Command.Manual", "pulse; Auto back; ManualPosition % in manual"),
              ("Outlet.HydraulicPump.Command.Start", "held, in manual; Stop the same"),
              ("Outlet.Cylinder[i].Command.Open", "jog, held while pressed; Close the same"),
              ("Outlet.Cylinder[i].Command.CalibrateClosed", "pulse; CalibrateOpen the same"),
              ("Outlet.Command.FaultReset", "pulse: resets the emergency stop latch")],
    status=[("Outlet.Status.Position", "with Setpoint, Mode, Fault, EmergencyStop"),
            ("Outlet.HydraulicPump.Status.Running", "with Available, FeedbackFault"),
            ("Outlet.Cylinder[i].Status.Position", "with Calibrated, CurrentState, Fault")],
    steps=["`Outlet.Status.EmergencyStop` FALSE, `Outlet.HydraulicPump.Status.Available` TRUE.",
           "Per cylinder: jog Open / Close, calibrate closed and open: Status.Calibrated TRUE.",
           "Auto, write Mode: all cylinders move to ModePosition; Status.Position follows."],
    alarms=["Outlet.Alarm", "Outlet.Cylinder[i].Alarm", "Outlet.HydraulicPump.Alarm"])

ORDER = ["S1", "S2", "S3", "S4", "S7", "S5", "S6"]

# Suggestions for node placement: (now, proposal, why)
SUGGEST = [
    ("`InletRIO[i]` top level, next to `Inlet[i]` and `OxySystem[i]`",
     "`Inlet[i].RIO` (or keep the array, but name it after the station)",
     "Inlet station i is one cabinet: its coupler, oxy pump drive link and the inlet sensors. Starting an inlet "
     "now needs three branches."),
    ("Drive link status in `InletRIO[i].Status.DriveDataStale` / DriveRestarts",
     "`OxySystem[i].OxyPump.Status` (next to CommunicationOK and AutoResets)",
     "Everything about the oxy pump drive in one place."),
    ("`LevelController` and `OxyController` top level, their settings in `Pen.Config.LevelController` / "
     "`Pen.Config.OxyController`",
     "`Pen.LevelController` and `Pen.OxyController`, settings in their own .Config",
     "LIC01 / OIC01 belong to the pen. `LevelController.Config` and `OxyController.Config` exist as well, but no "
     "reference to them was found in the program: two places for the same gains."),
    ("`PenInletSupervisor` top level and `Pen.InletSupervisor`",
     "keep `Pen.InletSupervisor` only (and `InletSequence` inside it)",
     "Same type twice; no reference to `Pen.InletSupervisor` was found in the program."),
    ("`Pen.Input.OxyConcentration[i]`, OxySaturation[i], Temperature[i], Salinity[i], TotalDissolvedSolids[i], "
     "Depth[i]",
     "remove; the values are in `Pen.Input.Orbit864Sensor[i]`",
     "No reference found in the program; a client reading them gets zeros."),
    ("`Pen.Command.InitModbusRTU` / `Pen.Status.ModbusRTUInitialised`",
     "`CommonRIO.Command` / `CommonRIO.Status` (the RTU settings are already in `CommonRIO.Config`)",
     "The serial bus to the Orbit sensors is CommonRIO's, not the pen's."),
    ("`Inlet[i].InletPump.Input` holds Start, Stop, Reset, VelocitySetpoint, HeartbeatToggle",
     "only measurements in Input; the outgoing signals in `Inlet[i].InletPump.InternalCommand` (already exists)",
     "Input reads like 'from the field'; commands there are easy to write by mistake."),
    ("`OxySystem[i].OxyValve.Command.AutoSetpoint` / Open / Close / SuppressAlarms written by the PLC",
     "an InternalCommand branch as for the inlet pump; Command for the operator only",
     "An operator writing AutoSetpoint is overwritten or fights the controller (GEN-13)."),
    ("Mains / battery inputs in both `Pen.Input` and `Inlet[i].Input` (MainCircuitBreakerTripped, BackupPowerOn, "
     "BatteryFault)",
     "one place: the cabinet they are wired in (inlet station i)",
     "Two nodes for one signal; the Pen copies are not filled."),
    ("`EmergencyStop` (BOOL, not implemented) top level",
     "remove",
     "A node that never changes looks like a healthy signal (GEN-12)."),
]


# ------------------------------------------------------------------------------------------- check
NODE = re.compile(r"`([A-Za-z_][\w\[\]\.]*)`")


def all_node_refs():
    for s in SYSTEMS:
        for p in s["branches"] + s["alarms"]:
            yield s["id"], p
        for p, note in s["settings"] + s["commands"] + s["status"]:
            yield s["id"], p
        for t in s["steps"] + [s["what"]] + [n for _, n in s["settings"] + s["commands"] + s["status"]]:
            for m in NODE.finditer(t):
                yield s["id"], m.group(1)
    for now, prop, why in SUGGEST:
        for t in (now, prop, why):
            for m in NODE.finditer(t):
                if not t is prop:          # proposals name nodes that do not exist yet
                    yield "suggestions", m.group(1)
    for _, t in CONVENTIONS:
        for m in NODE.finditer(t):
            yield "conventions", m.group(1)


def check(valid):
    bad = []
    for sid, p in all_node_refs():
        n = opc_paths.normalise(p)
        if n not in valid and n + "[i]" not in valid and not any(v.startswith(n + ".") for v in valid):
            bad.append((sid, p))
    return bad


# ------------------------------------------------------------------------------------------- render
ESC = re.compile(r"([\\|\[\]{}*_+^~#-])")


def wtext(t):
    parts = re.split(r"(`[^`]*`)", t)
    return "".join("{{" + ESC.sub(r"\\\1", p[1:-1]) + "}}" if p.startswith("`") and p.endswith("`")
                   else ESC.sub(r"\\\1", p) for p in parts)


def htext(t):
    parts = re.split(r"(`[^`]*`)", t)
    return "".join(f"<code>{html.escape(p[1:-1])}</code>" if p.startswith("`") and p.endswith("`")
                   else html.escape(p) for p in parts)


def wnode(p):
    return "{{" + ESC.sub(r"\\\1", p) + "}}"


def render(source):
    today = dt.date.today().isoformat()
    by = {s["id"]: s for s in SYSTEMS}
    W, H = [], []
    W.append("{info}Generated " + today + ", nodes checked against " + ESC.sub(r"\\\1", source) +
             ". Do not edit here: change commissioning_usecases.py in workfolder-latex/CAS/OPC UA interface "
             "and regenerate.{info}")
    W.append("{toc:maxLevel=2}")
    H.append(f"<p class='gen'>Generated {today}, nodes checked against {html.escape(source)}.</p>")
    W.append("h1. How to read this")
    W.append(wtext(INTRO))
    H.append("<h1>How to read this</h1><p>" + htext(INTRO) + "</p>")

    W.append("h2. Commands")
    W.append("|| Kind || How ||")
    H.append("<h2>Commands</h2><table><tr><th>Kind</th><th>How</th></tr>")
    for k, t in CONVENTIONS:
        W.append(f"| *{k}* | {wtext(t)} |")
        H.append(f"<tr><td><b>{k}</b></td><td>{htext(t)}</td></tr>")
    H.append("</table>")

    W.append("h1. Systems, in commissioning order")
    W.append("|| System || Open these branches || Settings || Commands || Status ||")
    H.append("<h1>Systems, in commissioning order</h1><table><tr><th>System</th><th>Open these branches</th>"
             "<th>Settings</th><th>Commands</th><th>Status</th></tr>")
    for i in ORDER:
        s = by[i]
        a = i.lower()
        W.append(f"| [{i} {wtext(s['name'])}|#{a}] | {', '.join(wnode(b) for b in s['branches'])} | "
                 f"{len(s['settings'])} | {len(s['commands'])} | {len(s['status'])} |")
        H.append(f"<tr><td><a href='#{a}'>{i} {html.escape(s['name'])}</a></td><td>"
                 f"{', '.join(f'<code>{html.escape(b)}</code>' for b in s['branches'])}</td>"
                 f"<td>{len(s['settings'])}</td><td>{len(s['commands'])}</td><td>{len(s['status'])}</td></tr>")
    H.append("</table>")

    for i in ORDER:
        s = by[i]
        a = i.lower()
        W.append(f"h2. {{anchor:{a}}}{i} {s['name']}")
        H.append(f"<h2 id='{a}'>{i} {html.escape(s['name'])}</h2>")
        W.append(wtext(s["what"]))
        H.append("<p>" + htext(s["what"]) + "</p>")
        W.append("*Open:* " + ", ".join(wnode(b) for b in s["branches"]) +
                 ("" if not s["alarms"] else "   *Alarms:* " + ", ".join(wnode(b) for b in s["alarms"])))
        H.append("<p><b>Open:</b> " + ", ".join(f"<code>{html.escape(b)}</code>" for b in s["branches"]) +
                 ("" if not s["alarms"] else "&nbsp;&nbsp; <b>Alarms:</b> " +
                  ", ".join(f"<code>{html.escape(b)}</code>" for b in s["alarms"])) + "</p>")
        W.append("|| || Node || What ||")
        H.append("<table class='card'><tr><th></th><th>Node</th><th>What</th></tr>")
        for label, key in (("Settings", "settings"), ("Commands", "commands"), ("Status", "status")):
            rows = s[key] or [("", "none")]
            for n, (p, note) in enumerate(rows):
                head = f"*{label}*" if n == 0 else " "
                W.append(f"| {head} | {wnode(p) if p else ' '} | {wtext(note)} |")
                hh = f"<th rowspan='{len(rows)}' class='{key}'>{label}</th>" if n == 0 else ""
                H.append(f"<tr>{hh}<td>{'<code>' + html.escape(p) + '</code>' if p else ''}</td>"
                         f"<td>{htext(note)}</td></tr>")
        H.append("</table>")
        W.append("*Start and verify*")
        H.append("<p><b>Start and verify</b></p><ol>")
        for t in s["steps"]:
            W.append("# " + wtext(t))
            H.append("<li>" + htext(t) + "</li>")
        H.append("</ol>")

    W.append("h1. Suggestions for node placement")
    W.append(wtext("Changes to the PLC's node structure that would let one system be started and verified in one "
                   "branch. Not implemented; a proposal for the PLC project. Proposed paths do not exist yet."))
    W.append("|| # || Now || Proposal || Why ||")
    H.append("<h1>Suggestions for node placement</h1><p>Changes to the PLC's node structure that would let one system "
             "be started and verified in one branch. Not implemented; a proposal for the PLC project. Proposed paths "
             "do not exist yet.</p><table><tr><th>#</th><th>Now</th><th>Proposal</th><th>Why</th></tr>")
    for n, (now, prop, why) in enumerate(SUGGEST, 1):
        W.append(f"| {n} | {wtext(now)} | {wtext(prop)} | {wtext(why)} |")
        H.append(f"<tr><td>{n}</td><td>{htext(now)}</td><td>{htext(prop)}</td><td>{htext(why)}</td></tr>")
    H.append("</table>")

    css = ("body{font-family:system-ui,sans-serif;max-width:1100px;margin:24px auto;padding:0 16px;color:#1f2328;"
           "background:#fff}table{border-collapse:collapse;width:100%;margin:6px 0 16px}th,td{border:1px solid #d0d7de;"
           "padding:4px 8px;vertical-align:top;font-size:13px;text-align:left}th{background:#f6f8fa}"
           "code{font-size:12px;background:#f6f8fa;padding:0 3px;border-radius:3px}.gen{color:#57606a}"
           "h2{border-top:1px solid #d0d7de;padding-top:12px}table.card td:nth-child(2){white-space:nowrap}"
           "th.settings{background:#eef6ee}th.commands{background:#fff4e5}th.status{background:#eef3fb}")
    page = ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>CAS commissioning use cases</title>"
            f"<style>{css}</style></head><body><h1>CAS (Heimdall): commissioning, system by system</h1>" +
            "\n".join(H) + "</body></html>")
    return "\n".join(W) + "\n", page


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    argv = argv or sys.argv[1:]
    repo = argv[0]
    valid = opc_paths.paths(repo)
    bad = check(valid)
    if bad:
        print(f"{len(bad)} node references not found in GVLMain:")
        for sid, p in bad:
            print(f"  {sid}: {p}")
    try:
        rev = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%h %cs"], capture_output=True, text=True,
                             check=True).stdout.strip()
    except Exception:   # noqa: BLE001
        rev = "unknown revision"
    wiki, page = render(f"scaleaq/heimdall-plc {rev}")
    open(OUT_WIKI, "w", encoding="utf-8").write(wiki)
    open(OUT_HTML, "w", encoding="utf-8").write(page)
    print(f"{len(SYSTEMS)} systems, {sum(1 for _ in all_node_refs())} node references checked; wrote", OUT_WIKI)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
