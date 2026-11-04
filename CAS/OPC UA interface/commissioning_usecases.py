"""CAS commissioning use cases: which OPC UA nodes to write and read, and in which order.

    py commissioning_usecases.py <heimdall-plc checkout>

Structured after J. Cooling, Software Engineering for Real-Time Systems (2020), sec. 3.4.5 (use case
analysis) and 7.3.1 (use case diagrams): a use case model of actors and use cases, and for each use case a
text description from START to FINISH with the normal scenario, scenarios with errors handled in the
interaction (alternatives) and errors that end it (exceptions), plus include / extend relationships.

Every node written in backticks in the texts below is checked against the PLC project (GVLMain, the only node
structure exposed over OPC UA). Array indices are 0-based on the server: Inlet[0] is inlet 1.

Writes next to this script:
    CAS commissioning use cases.confluence.txt   Confluence wiki markup (Insert > Markup > Confluence wiki)
    CAS commissioning use cases.html             the same for review in a browser
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import sys

import opc_paths

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_WIKI = os.path.join(HERE, "CAS commissioning use cases.confluence.txt")
OUT_HTML = os.path.join(HERE, "CAS commissioning use cases.html")

ACTORS = [
    ("Commissioning engineer", "primary",
     "Runs field test / commissioning. Works through an OPC UA client: the CAS HMI, UaExpert, or a SiteControl "
     "service. Direct actor of the PLC is the OPC UA client; the engineer is the indirect actor (Cooling 3.4.5 c)."),
    ("Operator", "primary", "Runs the pen after commissioning (same use cases UC-05 to UC-07, without the tests)."),
    ("SiteControl", "external system",
     "Reads plant values and alarms, may send commands. Must follow 'CAS requirements for OPC UA clients of the "
     "PLC' (one session, subscriptions, reconnect, read-only mode)."),
    ("Framo pump controller (PCC 1..3)", "external system",
     "Inlet pump controllers; the PLC is their OPC UA client (data sources Framo_1..3)."),
    ("Remote I/O and drives", "external system",
     "CommonRIO and InletRIO 1..3 (Wago 750-362, Modbus TCP), oxy pump drives (ATV650, Modbus TCP), Orbit 864 "
     "O2 sensors (Modbus RTU via the 750-652)."),
    ("Supplier technicians", "secondary",
     "Framo (inlet pumps), Servi / Østerbø (outlet hydraulics), Normex (O2 supply): present when their "
     "equipment is commissioned."),
]

# Each use case: id, name, goal, level, actors, includes, extends, pre, start, main, alt, exc, finish,
# write, read, config, open. Steps are (who, text); nodes in backticks.
UC = []


def uc(**k):
    UC.append(k)


uc(id="UC-00", name="Connect to the PLC", level="subfunction (included by all)",
   goal="An OPC UA session to the PLC with GVLMain found and a monitoring list running.",
   actors=["Commissioning engineer", "SiteControl"], includes=[], extends=[],
   pre=["PLC powered, application running (CODESYS: RUN).",
        "Client has its own PLC user account (anonymous access is off, register GEN-11)."],
   start="The engineer starts the OPC UA client and connects to opc.tcp://<PLC IP>:4840.",
   main=[("Client", "Logs in with its user (SecurityPolicy None today: password unencrypted, test network only)."),
         ("Client", "Browses once for GVLMain (node id ns=4;s=|var|<device>.Application.GVLMain); derives all "
                    "other paths from it."),
         ("Client", "Creates one subscription (>= 1 s, queue size 1) with the monitoring list of the use case "
                    "at hand; always includes `Pen.Status.State`, `Pen.Status.Ready`, `Pen.Status.CommandRejected`."),
         ("Client", "Writes FALSE to every command bit it may have left TRUE in an earlier session.")],
   alt=[("Node not found", [("Client", "Logs it once, shows it as 'not available', looks it up again after a "
                                       "download or every 10 min (client requirements CON-05).")])],
   exc=[("Login refused (BadUserAccessDenied / BadIdentityTokenInvalid)",
         [("Engineer", "Checks user, password and the user's symbol rights in CODESYS. FINISH (abandoned).")])],
   finish="Session up, GVLMain found, monitoring list running.",
   write=[], read=["Pen.Status.State", "Pen.Status.Ready", "Pen.Status.CommandRejected"], config=[],
   open=["GEN-11 (encryption before site)", "GEN-06 (PLC CPU load and state in GVLMain)"])

uc(id="UC-01", name="Configure and verify field communication", level="user goal",
   goal="Every remote I/O, oxy pump drive and Framo controller connected, with fresh data.",
   actors=["Commissioning engineer", "Remote I/O and drives", "Framo pump controller (PCC 1..3)"],
   includes=["UC-00"], extends=[],
   pre=["Network installed; IP plan known (register IN-25).", "Devices powered."],
   start="The engineer opens the communication settings.",
   main=[("Engineer", "Writes the CommonRIO address: `CommonRIO.Config.IP`, `CommonRIO.Config.Port` (502), then "
                      "`CommonRIO.Config.Enabled` := TRUE."),
         ("Engineer", "For each inlet station i (0..2): `InletRIO[i].Config.IP`, `InletRIO[i].Config.Port`, "
                      "`InletRIO[i].Config.Enabled` := TRUE."),
         ("Engineer", "For each oxy pump drive: `InletRIO[i].Config.DriveIP`, `InletRIO[i].Config.DrivePort`, "
                      "`InletRIO[i].Config.DriveUnitId`, then `InletRIO[i].Config.DriveEnabled` := TRUE."),
         ("Engineer", "For each Framo controller: `Inlet[i].Config.FramoIP`, `Inlet[i].Config.FramoPort`, "
                      "`Inlet[i].Config.FramoUpdateRate`."),
         ("PLC", "Connects. Settings are retained (survive a restart); a changed IP or port makes the master "
                 "reconnect."),
         ("Engineer", "Verifies: drive `OxySystem[i].OxyPump.Status.CommunicationOK` TRUE; Framo "
                      "`Inlet[i].InletPump.Status.FramoConnected` and `Inlet[i].InletPump.Status.CommunicationOK` "
                      "TRUE, `Inlet[i].InletPump.Status.FramoEndpoint` shows the address in use."),
         ("Engineer", "Verifies the RIO links indirectly: the station's sensors leave bad quality, e.g. "
                      "`Inlet[i].Input.LevelInsidePen.Status.BadQuality` FALSE; CommonRIO: "
                      "`OxySystem[i].Input.OxygenFlow.Status.BadQuality` FALSE.")],
   alt=[("A drive reports a communication-loss fault after connecting (LFT 150 EtHF)",
         [("PLC", "Resets it automatically once per link recovery (`OxySystem[i].OxyPump.Status.AutoResets` "
                  "counts up). Other faults: UC-06 step 'reset drive'.")]),
        ("Framo link up but heartbeat not answered",
         [("PLC", "`Inlet[i].InletPump.Alarm.HeartbeatTimeout` raised, pump shown Unavailable. Engineer checks "
                  "the PCC with Framo (IN-02).")])],
   exc=[("Device not reachable", [("Engineer", "Checks cabling, IP and port. FINISH (abandoned) for that device.")])],
   finish="All devices connected; no communication alarm.",
   write=["CommonRIO.Config.IP", "CommonRIO.Config.Port", "CommonRIO.Config.Enabled", "InletRIO[i].Config.IP",
          "InletRIO[i].Config.Port", "InletRIO[i].Config.Enabled", "InletRIO[i].Config.DriveIP",
          "InletRIO[i].Config.DrivePort", "InletRIO[i].Config.DriveUnitId", "InletRIO[i].Config.DriveEnabled",
          "Inlet[i].Config.FramoIP", "Inlet[i].Config.FramoPort", "Inlet[i].Config.FramoUpdateRate"],
   read=["OxySystem[i].OxyPump.Status.CommunicationOK", "Inlet[i].InletPump.Status.FramoConnected",
         "Inlet[i].InletPump.Status.CommunicationOK", "Inlet[i].InletPump.Status.FramoEndpoint",
         "Inlet[i].InletPump.Status.FramoRestarts", "OxySystem[i].OxyPump.Status.AutoResets"],
   config=[],
   open=["IN-40 (frozen links, watchdog)", "IN-25 (IP plan)",
         "Coupler watchdog (CouplerWatchdog): with each RIO linked, InletRIO[i].Status.Watchdog.State and "
         "CommonRIO.Status.Watchdog.State read 1 (active); check on a real 750-362 that the FC3 status read keeps "
         "it alive (OX-40)"])

uc(id="UC-02", name="Verify instruments", level="user goal",
   goal="Every transmitter reads a plausible value with good quality and the right scaling.",
   actors=["Commissioning engineer"], includes=["UC-00", "UC-01"], extends=[],
   pre=["UC-01 finished.", "Instrument data sheets at hand (range, signal direction)."],
   start="The engineer selects an instrument.",
   main=[("Engineer", "Level transmitters (inside / outside per inlet): checks the range "
                      "`Inlet[i].Input.LevelInsidePen.Config.MinValue` / `Inlet[i].Input.LevelInsidePen.Config.MaxValue` "
                      "(and the same for `Inlet[i].Input.LevelOutsidePen`) against the data sheet; reads "
                      "`Inlet[i].Input.LevelInsidePen.ScaledRaw`, `Inlet[i].Input.LevelInsidePen.Filtered` and "
                      "`Inlet[i].Input.LevelInsidePen.Status.BadQuality`; compares with a manual measurement."),
         ("Engineer", "Checks the pen values the controllers use: `Pen.Input.AverageOverHeight.Filtered`, "
                      "`Pen.Status.OverHeight`, `Pen.Status.LevelControlOK`."),
         ("Engineer", "O2 sensors (Orbit 864): `Pen.Input.Orbit864Sensor[i].Config.SlaveAddress`, "
                      "`Pen.Input.Orbit864Sensor[i].Config.Enabled`, `Pen.Input.Orbit864Sensor[i].Config.StayAwake`; "
                      "verifies `Pen.Input.Orbit864Sensor[i].Status.CommOK` and the values "
                      "`Pen.Input.OxyConcentration[i].Filtered`, `Pen.Input.Temperature[i].Filtered`."),
         ("Engineer", "Chooses the O2 sensors for control: `Pen.Input.Orbit864Sensor[i].Config.EnableForAutoControl`; "
                      "checks `Pen.Status.PenOxygenLevel` and `Pen.Status.OxyControlOK`."),
         ("Engineer", "Oxygen line instruments: `OxySystem[i].Input.OxyPumpPressure.Filtered`, "
                      "`OxySystem[i].Input.OxynatorOutletPressure.Filtered`, `OxySystem[i].Input.OxygenFlow.Filtered`."),
         ("Engineer", "Pen water quality: `Pen.Input.CO2.Filtered`, `Pen.Input.TotalGasPressure.Filtered`.")],
   alt=[("Reading inverted or offset", [("Engineer", "Corrects MinValue / MaxValue (signal direction, IN-24), "
                                                     "checks again.")]),
        ("An Orbit 864 address changed", [("Engineer", "SlaveAddress is read only at PLC start-up: restart the "
                                                       "PLC (or download), then verify.")])],
   exc=[("Transmitter dead or wired wrong", [("Engineer", "BadQuality stays TRUE: raise a deviation in the register. "
                                                          "FINISH (abandoned) for that instrument.")])],
   finish="All instruments verified; deviations in the register.",
   write=["Inlet[i].Input.LevelInsidePen.Config.MinValue", "Inlet[i].Input.LevelInsidePen.Config.MaxValue",
          "Pen.Input.Orbit864Sensor[i].Config.SlaveAddress", "Pen.Input.Orbit864Sensor[i].Config.Enabled",
          "Pen.Input.Orbit864Sensor[i].Config.EnableForAutoControl"],
   read=["Inlet[i].Input.LevelInsidePen.Filtered", "Inlet[i].Input.LevelInsidePen.Status.BadQuality",
         "Inlet[i].Input.LevelOutsidePen.Filtered", "Pen.Status.OverHeight", "Pen.Status.LevelControlOK",
         "Pen.Input.Orbit864Sensor[i].Status.CommOK", "Pen.Input.OxyConcentration[i].Filtered",
         "Pen.Status.PenOxygenLevel", "OxySystem[i].Input.OxyPumpPressure.Filtered",
         "OxySystem[i].Input.OxygenFlow.Filtered"],
   config=[],
   open=["IN-24 (level transmitter signal direction)", "IN-39 (level span for waves)", "OX-36 (total gas pressure)",
         "IN-48 (CO2)"])

uc(id="UC-03", name="Commission the outlet dampers", level="user goal",
   goal="All four cylinders calibrated, moving in both directions, and the outlet following the operation mode.",
   actors=["Commissioning engineer", "Supplier technicians"], includes=["UC-00", "UC-01"], extends=[],
   pre=["Hydraulic unit filled and checked by Servi / Østerbø.", "Emergency stop released.",
        "Cylinder pressure transmitters and flow counters verified (UC-02)."],
   start="The engineer puts the hydraulic pump in manual.",
   main=[("Engineer", "Hydraulic pump: pulse `Outlet.HydraulicPump.Command.Manual`, check "
                      "`Outlet.HydraulicPump.Status.Available`, pulse `Outlet.HydraulicPump.Command.Start`, "
                      "check `Outlet.HydraulicPump.Status.Running`; pulse `Outlet.HydraulicPump.Command.Stop`; "
                      "then `Outlet.HydraulicPump.Command.Auto` (in auto it runs on cylinder demand)."),
         ("Engineer", "Per cylinder i (0..3): pulse `Outlet.Cylinder[i].Command.Manual`; jog closed with "
                      "`Outlet.Cylinder[i].Command.Close` held TRUE until the closed end, then FALSE."),
         ("Engineer", "At the closed end: pulse `Outlet.Cylinder[i].Command.CalibrateClosed`; wait until "
                      "`Outlet.Cylinder[i].Status.CounterSetRequest` is FALSE and "
                      "`Outlet.Cylinder[i].Status.Calibrated` TRUE."),
         ("Engineer", "Jog open with `Outlet.Cylinder[i].Command.Open` held TRUE until "
                      "`Outlet.Cylinder[i].Status.CurrentState` = Opened (pressure-confirmed end), then FALSE; "
                      "pulse `Outlet.Cylinder[i].Command.CalibrateOpen`."),
         ("Engineer", "Tests positioning: `Outlet.Cylinder[i].Command.ManualSetpoint` := 50, checks "
                      "`Outlet.Cylinder[i].Status.Position`; then pulse `Outlet.Cylinder[i].Command.Auto`."),
         ("Engineer", "Outlet as a whole: sets the openings per mode `Outlet.Config.ModePosition` (register OUT-10), "
                      "selects `Outlet.Command.Mode` (0 O-35, 1 O-45, 2 O-60, 3 S-75), pulse `Outlet.Command.Auto`; "
                      "checks `Outlet.Status.Setpoint`, `Outlet.Status.Position`, `Outlet.Status.Mode`.")],
   alt=[("Emergency stop was pressed", [("Engineer", "Releases it, pulse `Outlet.Command.FaultReset`, checks "
                                                     "`Outlet.Status.EmergencyStop` FALSE.")]),
        ("Hydraulic pump feedback fault", [("Engineer", "Pulse `Outlet.HydraulicPump.Command.Reset`.")]),
        ("Counter set not confirmed (`Outlet.Cylinder[i].Status.CounterSetFailed`)",
         [("Engineer", "Acknowledge `Outlet.Cylinder[i].AlarmAck.FlowSensorFault` (TRUE then FALSE), repeat "
                       "CalibrateClosed.")])],
   exc=[("Cylinder moves the wrong way or travel timeout", [("Engineer", "Stops (release jog), checks valves and "
                                                                         "wiring with Servi. FINISH (abandoned).")])],
   finish="Cylinders calibrated and in auto; outlet follows the mode.",
   write=["Outlet.HydraulicPump.Command.Manual", "Outlet.HydraulicPump.Command.Start",
          "Outlet.HydraulicPump.Command.Stop", "Outlet.HydraulicPump.Command.Auto",
          "Outlet.Cylinder[i].Command.Manual", "Outlet.Cylinder[i].Command.Open", "Outlet.Cylinder[i].Command.Close",
          "Outlet.Cylinder[i].Command.CalibrateClosed", "Outlet.Cylinder[i].Command.CalibrateOpen",
          "Outlet.Cylinder[i].Command.ManualSetpoint", "Outlet.Cylinder[i].Command.Auto", "Outlet.Config.ModePosition",
          "Outlet.Command.Mode", "Outlet.Command.Auto", "Outlet.Command.FaultReset"],
   read=["Outlet.HydraulicPump.Status.Available", "Outlet.HydraulicPump.Status.Running",
         "Outlet.Cylinder[i].Status.Calibrated", "Outlet.Cylinder[i].Status.CurrentState",
         "Outlet.Cylinder[i].Status.Position", "Outlet.Cylinder[i].Input.PressureOpen",
         "Outlet.Cylinder[i].Input.PressureClose", "Outlet.Status.Setpoint", "Outlet.Status.Position",
         "Outlet.Status.Fault", "Outlet.Status.EmergencyStop"],
   config=["Outlet.Config.ModePosition", "Outlet.Cylinder[i].Config.MaxPressureOpen"],
   open=["OUT-10 (mode openings)", "OUT-13 (outputs on comm loss)", "Outlet logic is Bjørn's (OutletControl)"])

uc(id="UC-04", name="Commission an inlet pump in manual", level="user goal",
   goal="Inlet pump i starts, runs at the speed set from the PLC, and stops, under PLC control.",
   actors=["Commissioning engineer", "Framo pump controller (PCC 1..3)", "Supplier technicians"],
   includes=["UC-00", "UC-01"], extends=[],
   pre=["Framo has commissioned the pump locally; PCC in remote.", "Outlet open (UC-03) so the pen is not "
        "overfilled.", "Framo link up (UC-01)."],
   start="The engineer selects inlet pump i.",
   main=[("Engineer", "Checks the supervision times: `Inlet[i].Config.StartupTime`, `Inlet[i].Config.ShutdownTime`, "
                      "`Inlet[i].Config.SpeedDeviationLimit`, `Inlet[i].Config.SpeedDeviationDelay`."),
         ("Engineer", "Pulse `Inlet[i].InletPump.Command.Manual`; checks `Inlet[i].InletPump.Status.Manual` TRUE."),
         ("Engineer", "Writes the speed `Inlet[i].InletPump.Command.Setpoint` (rpm, 40..130)."),
         ("Engineer", "Writes `Inlet[i].InletPump.Command.Start` := TRUE (the PLC clears it once the pump starts)."),
         ("PLC/Framo", "`Inlet[i].InletPump.State` goes Available (0) -> Starting (1) -> Remote (2); "
                       "`Inlet[i].InletPump.Status.ActualSpeed` follows the setpoint in Remote."),
         ("Engineer", "Changes the setpoint in steps; checks speed and `Inlet[i].InletPump.Input.MotorCurrent`, "
                      "`Inlet[i].InletPump.Input.MotorPower`."),
         ("Engineer", "Writes `Inlet[i].InletPump.Command.Stop` := TRUE; State -> Stopping (3) -> Available (0) "
                      "(the PLC clears Stop)."),
         ("Engineer", "Pulse `Inlet[i].InletPump.Command.Auto` (or leaves it in manual until UC-05).")],
   alt=[("Pump in Hold (4) or Lockdown (5)",
         [("Engineer", "Fixes the cause with Framo, pulse `Inlet[i].InletPump.Command.Reset`; the PLC holds the "
                       "reset until the state changes, else `Inlet[i].InletPump.Alarm.FailedToReset`.")]),
        ("Pump does not start within StartupTime", [("PLC", "`Inlet[i].InletPump.Alarm.StartUpTimeout`.")])],
   exc=[("Unavailable (9): link or PCC not ready", [("Engineer", "Back to UC-01. FINISH (abandoned).")])],
   finish="Pump verified in manual; left in auto or manual as planned.",
   write=["Inlet[i].InletPump.Command.Manual", "Inlet[i].InletPump.Command.Setpoint",
          "Inlet[i].InletPump.Command.Start", "Inlet[i].InletPump.Command.Stop", "Inlet[i].InletPump.Command.Reset",
          "Inlet[i].InletPump.Command.Auto"],
   read=["Inlet[i].InletPump.State", "Inlet[i].InletPump.Status.Manual", "Inlet[i].InletPump.Status.ActualSpeed",
         "Inlet[i].InletPump.Input.MotorCurrent", "Inlet[i].InletPump.Alarm.StartUpTimeout",
         "Inlet[i].InletPump.Alarm.SpeedDeviation"],
   config=["Inlet[i].Config.StartupTime", "Inlet[i].Config.ShutdownTime", "Inlet[i].Config.SpeedDeviationLimit"],
   open=["IN-42: Framo has removed the pump state machine; the states above will be derived by the PLC from "
         "status bits", "IN-41 (heartbeat loss stops the pump)", "IN-43 (start timing)", "GEN-13 (a Start "
         "written in auto stays set)"])

uc(id="UC-05", name="Start the pen and commission level control", level="user goal",
   goal="The pen running with the inlet pumps in auto and LIC01 holding the over-height at the setpoint.",
   actors=["Commissioning engineer", "Operator", "Framo pump controller (PCC 1..3)"],
   includes=["UC-00", "UC-02"], extends=[],
   pre=["UC-03 and UC-04 finished for the pumps in service.", "Outlet in auto at the chosen mode."],
   start="The engineer prepares the pumps for automatic operation.",
   main=[("Engineer", "Per pump in service: `Inlet[i].Config.InletPumpEnable` := TRUE and pulse "
                      "`Inlet[i].InletPump.Command.Auto`."),
         ("Engineer", "Sets `Pen.Command.LevelSetpoint` (m over-height, e.g. 0.06) and checks LIC01 tuning "
                      "`Pen.Config.LevelController.Kp`, `Pen.Config.LevelController.Ti`, "
                      "`Pen.Config.LevelController.MinOutput`, `Pen.Config.LevelController.MaxOutput`."),
         ("Engineer", "Checks the pump count settings `Pen.Config.PumpTargetSpeed`, `Pen.Config.PumpAddSpeed`, "
                      "`Pen.Config.PumpRemoveDelay`, `Pen.Config.PumpAddDelay`, `Pen.Config.PumpCycleTime`."),
         ("Engineer", "Waits for `Pen.Status.Ready` TRUE (a pump in auto is Available AND a valid level pair)."),
         ("Engineer", "Pulse `Pen.Command.Start`."),
         ("PLC", "`Pen.Status.State` Stopped (0) -> Starting (1): all candidate pumps start, LIC01 tracks their "
                 "speed; -> Running (2) when a pump is in Remote; LIC01 to auto, bumpless."),
         ("Engineer", "Monitors `Pen.Status.OverHeight` against `Pen.Command.LevelSetpoint`, "
                      "`LevelController.Output.OUT` (total rpm), `PenInletSupervisor.AutoSpeedSetpoint` (rpm per "
                      "pump), `PenInletSupervisor.PumpsWanted`."),
         ("Engineer", "Tests LIC01 manual: pulse `LevelController.Command.Manual`, write "
                      "`LevelController.Command.ManualOutput` (rpm per pump), then pulse `LevelController.Command.Auto` "
                      "(the PLC sets the setpoint to the current level, bumpless).")],
   alt=[("`Pen.Status.CommandRejected` TRUE after Start", [("Engineer", "Ready was FALSE: checks pumps in auto and "
                                                                        "level quality, starts again.")]),
        ("Level outside the band for the delay", [("PLC", "`Pen.Alarm.LevelDeviationHigh` / "
                                                          "`Pen.Alarm.LevelDeviationLow` "
                                                          "(`Pen.Config.LevelDeviationLimit`, `Pen.Config.LevelDeviationDelay`).")])],
   exc=[("All level pairs lost", [("PLC", "`Pen.Alarm.LevelMeasurementLost`, LIC01 to its safe output. Engineer "
                                          "stops the pen (UC-10). FINISH (abandoned).")])],
   finish="Pen Running, level at setpoint, pump count and rotation active.",
   write=["Inlet[i].Config.InletPumpEnable", "Inlet[i].InletPump.Command.Auto", "Pen.Command.LevelSetpoint",
          "Pen.Command.Start", "LevelController.Command.Manual", "LevelController.Command.ManualOutput",
          "LevelController.Command.Auto"],
   read=["Pen.Status.Ready", "Pen.Status.State", "Pen.Status.CommandRejected", "Pen.Status.OverHeight",
         "LevelController.Output.OUT", "LevelController.Status.Manual", "PenInletSupervisor.AutoSpeedSetpoint",
         "PenInletSupervisor.PumpsWanted", "PenInletSupervisor.PumpRotationActive", "Inlet[i].InletPump.State",
         "Pen.Alarm.LevelDeviationHigh", "Pen.Alarm.LevelMeasurementLost"],
   config=["Pen.Config.LevelController.Kp", "Pen.Config.LevelController.Ti", "Pen.Config.PumpTargetSpeed",
           "Pen.Config.PumpAddSpeed", "Pen.Config.PumpRemoveDelay", "Pen.Config.PumpAddDelay",
           "Pen.Config.PumpCycleTime", "Pen.Config.LevelDeviationLimit"],
   open=["IN-47 (pump count timers and next pump not visible)", "IN-22 (setpoint per mode)", "IN-23 (restart "
         "after power failure)", "IN-20 (interlocks I2 / I3)"])

uc(id="UC-06", name="Commission an oxygen line", level="user goal",
   goal="Oxygen line i: oxy pump holding pressure, valve and flow controller adding O2 on demand.",
   actors=["Commissioning engineer", "Supplier technicians", "Remote I/O and drives"],
   includes=["UC-00", "UC-01", "UC-02"], extends=[],
   pre=["Normex O2 supply commissioned, manual valves open.", "Inlet pump i in Remote (UC-05): oxygen is added "
        "only while the inlet pump runs.", "Pen Running."],
   start="The engineer selects oxygen line i.",
   main=[("Engineer", "Checks the line settings: `OxySystem[i].Config.PressureSetpoint` (bar), "
                      "`OxySystem[i].Config.OxyPump.MinSpeed_Hz`, `OxySystem[i].Config.OxyPump.MaxSpeed_Hz`, "
                      "`OxySystem[i].Config.OxyPump.PresetSpeed_Hz`, `OxySystem[i].Config.OxyPump.RunDelay`, "
                      "`OxySystem[i].Config.ValveOpenPressure`, `OxySystem[i].Config.FlowMax`."),
         ("Engineer", "Oxy pump test in manual: pulse `OxySystem[i].OxyPump.Command.Manual`, write "
                      "`OxySystem[i].OxyPump.Command.Setpoint` (Hz), write `OxySystem[i].OxyPump.Command.Start` := TRUE; "
                      "checks `OxySystem[i].OxyPump.State`, `OxySystem[i].OxyPump.Status.ActualSpeed`, "
                      "`OxySystem[i].Input.OxyPumpPressure.Filtered`. Caution: in manual the pump runs without the "
                      "inlet permit (GEN-13)."),
         ("Engineer", "Writes `OxySystem[i].OxyPump.Command.Stop` := TRUE, then pulse "
                      "`OxySystem[i].OxyPump.Command.Auto`."),
         ("Engineer", "Enables the line: `OxySystem[i].Config.Enable` := TRUE; checks the permit "
                      "`Inlet[i].InletPump.Status.OxyPermit` TRUE."),
         ("Engineer", "Pulse `Pen.Command.OxygenStart` (UC-07 step 1)."),
         ("PLC", "Oxy pump starts at preset speed, PIC takes the pressure to the setpoint; after RunDelay with "
                 "pressure: `OxySystem[i].Status.ValvePermit` and `OxySystem[i].Status.OxygenationActive` TRUE."),
         ("Engineer", "Valve test in manual (only now the valve may open): pulse "
                      "`OxySystem[i].OxyValve.Command.Manual`, write `OxySystem[i].OxyValve.Command.ManualSetpoint` "
                      "(%), checks `OxySystem[i].Status.OxyValvePosition` and `OxySystem[i].Status.OxyFlow`; then "
                      "pulse `OxySystem[i].OxyValve.Command.Auto`."),
         ("Engineer", "Checks the line in auto: `OxySystem[i].Status.InAuto` TRUE, `OxySystem[i].Status.FlowSetpoint` "
                      "(its share of OIC01) followed by `OxySystem[i].Status.OxyFlow`.")],
   alt=[("Drive in fault", [("Engineer", "Fixes the cause, writes `OxySystem[i].OxyPump.Command.Reset` TRUE then FALSE "
                                         "(edge; the PLC does not clear it). Acknowledging DriveError does not reset "
                                         "the drive.")]),
        ("Pressure not reached", [("PLC", "Valve stays closed, `OxySystem[i].Alarm.ValvePressureLow`. Engineer checks "
                                          "the pump and the PressureSetpoint against the pump head (OX-19).")])],
   exc=[("Inlet pump stops", [("PLC", "Permit lost: valve closed, oxy pump stopped (auto). FINISH (abandoned) until "
                                      "the inlet pump runs again.")])],
   finish="Line in auto, adding the flow OIC01 asks for.",
   write=["OxySystem[i].OxyPump.Command.Manual", "OxySystem[i].OxyPump.Command.Setpoint",
          "OxySystem[i].OxyPump.Command.Start", "OxySystem[i].OxyPump.Command.Stop", "OxySystem[i].OxyPump.Command.Auto",
          "OxySystem[i].OxyPump.Command.Reset", "OxySystem[i].Config.Enable", "OxySystem[i].OxyValve.Command.Manual",
          "OxySystem[i].OxyValve.Command.ManualSetpoint", "OxySystem[i].OxyValve.Command.Auto"],
   read=["OxySystem[i].OxyPump.State", "OxySystem[i].OxyPump.Status.ActualSpeed",
         "OxySystem[i].Input.OxyPumpPressure.Filtered", "Inlet[i].InletPump.Status.OxyPermit",
         "OxySystem[i].Status.ValvePermit", "OxySystem[i].Status.OxygenationActive", "OxySystem[i].Status.InAuto",
         "OxySystem[i].Status.FlowSetpoint", "OxySystem[i].Status.OxyFlow", "OxySystem[i].Status.OxyValvePosition",
         "OxySystem[i].OxyPump.Input.LastFault", "OxySystem[i].Alarm.ValvePressureLow"],
   config=["OxySystem[i].Config.PressureSetpoint", "OxySystem[i].Config.OxyPump.MinSpeed_Hz", "OxySystem[i].Config.OxyPump.MaxSpeed_Hz",
           "OxySystem[i].Config.OxyPump.PresetSpeed_Hz", "OxySystem[i].Config.OxyPump.RunDelay", "OxySystem[i].Config.ValveOpenPressure",
           "OxySystem[i].Config.FlowMax"],
   open=["OX-32 (permit without a Framo REMOTE state)", "OX-35 (O2 per line vs water flow)", "OX-37 (injection "
         "point)", "GEN-12 (`OxySystem[i].Status.State` is never written)", "GEN-13"])

uc(id="UC-07", name="Commission pen oxygen control", level="user goal",
   goal="OIC01 holding the pen O2 at the setpoint by sharing the O2 flow over the lines.",
   actors=["Commissioning engineer", "Operator"], includes=["UC-00", "UC-02"], extends=[],
   pre=["UC-06 finished for the lines in service.", "Control sensors chosen (UC-02)."],
   start="The engineer switches oxygenation on.",
   main=[("Engineer", "Pulse `Pen.Command.OxygenStart` (accepted in Starting / Running); checks "
                      "`Pen.Status.OxygenOn` TRUE (after a PLC restart it is FALSE again, OX-33)."),
         ("Engineer", "Sets `Pen.Config.OxySetpoint` (mg/L) and checks OIC01 tuning `Pen.Config.OxyController.Kp`, "
                      "`Pen.Config.OxyController.Ti`."),
         ("Engineer", "Monitors `Pen.Status.PenOxygenLevel`, `OxyController.Output.OUT` (total kg/h), "
                      "`PenInletSupervisor.NumberOfInletsEnabledForOxyControl`, and per line "
                      "`OxySystem[i].Status.FlowSetpoint` / `OxySystem[i].Status.OxyFlow`."),
         ("Engineer", "Tests OIC01 manual: pulse `OxyController.Command.Manual`, write "
                      "`OxyController.Command.ManualOutput` (kg/h total), then pulse `OxyController.Command.Auto` "
                      "(the PLC sets the setpoint to the current O2, bumpless)."),
         ("Engineer", "Ends the test with the setpoint wanted for operation.")],
   alt=[("`Pen.Status.CommandRejected` after OxygenStart", [("Engineer", "The pen was not Starting / Running: "
                                                                         "UC-05 first.")])],
   exc=[("No good control sensor (`Pen.Status.OxyControlOK` FALSE)", [("PLC", "OIC01 holds its output "
                                                                              "(OX-08). Engineer fixes the sensors. "
                                                                              "FINISH (abandoned).")])],
   finish="Oxygenation on in auto.",
   write=["Pen.Command.OxygenStart", "Pen.Config.OxySetpoint", "OxyController.Command.Manual",
          "OxyController.Command.ManualOutput", "OxyController.Command.Auto"],
   read=["Pen.Status.OxygenOn", "Pen.Status.PenOxygenLevel", "Pen.Status.OxyControlOK", "OxyController.Output.OUT",
         "OxyController.Status.Manual", "PenInletSupervisor.NumberOfInletsEnabledForOxyControl",
         "OxySystem[i].Status.FlowSetpoint", "OxySystem[i].Status.OxyFlow"],
   config=["Pen.Config.OxySetpoint", "Pen.Config.OxyController.Kp", "Pen.Config.OxyController.Ti"],
   open=["OX-33 (oxygenation not restored after a restart)", "OX-34 (emergency oxygenation)", "OX-06 / OX-35 "
         "(high O2 limits)", "OX-07 (setpoint and unit)"])

uc(id="UC-08", name="Check and acknowledge alarms", level="subfunction (extends UC-01 to UC-07)",
   goal="Every alarm raised during a test is seen, understood and acknowledged.",
   actors=["Commissioning engineer", "Operator", "SiteControl"], includes=["UC-00"], extends=["UC-01 .. UC-07"],
   pre=["Session up (UC-00)."], start="An alarm changes state.",
   main=[("Client", "Reads the alarm byte, e.g. `Inlet[i].InletPump.Alarm.StartUpTimeout` (AlarmState: 0 Normal, "
                    "1 Unacknowledged, 2 Acknowledged, 3 RetainUnacknowledged, 4 Suppressed)."),
         ("Engineer", "Finds and fixes the cause."),
         ("Engineer", "Acknowledges with a rising edge on the matching ack bit, e.g. "
                      "`Inlet[i].InletPump.AlarmAck.StartUpTimeout` TRUE, then FALSE (the PLC never clears ack "
                      "bits)."),
         ("PLC", "1 -> 2 while the condition is present, -> 0 once it is gone.")],
   alt=[("Oxy pump drive fault", [("Engineer", "Ack does not reset the drive: `OxySystem[i].OxyPump.Command.Reset` "
                                               "(UC-06).")]),
        ("Hydraulic pump feedback fault", [("Engineer", "Needs `Outlet.HydraulicPump.Command.Reset`, not an ack.")])],
   exc=[], finish="No unacknowledged alarm; causes recorded.",
   write=["Inlet[i].InletPump.AlarmAck.StartUpTimeout"], read=["Inlet[i].InletPump.Alarm.StartUpTimeout"], config=[],
   open=["GEN-02 (alarm priorities and ack classes)", "GEN-12 (alarms that can never be raised)"])

uc(id="UC-09", name="Fault tests", level="user goal (extends UC-05 to UC-07)",
   goal="The planned failures give the designed reaction.",
   actors=["Commissioning engineer", "Supplier technicians"], includes=["UC-00", "UC-08"], extends=["UC-05 .. UC-07"],
   pre=["Pen Running with oxygenation (UC-05..07).", "Test plan agreed (who pulls which cable, when)."],
   start="The engineer announces the test.",
   main=[("Engineer", "Framo link of one pump down: expects `Inlet[i].InletPump.Alarm.HeartbeatTimeout`, "
                      "`Inlet[i].InletPump.Status.CommunicationOK` FALSE, oxygen line i stops "
                      "(`Inlet[i].InletPump.Status.OxyPermit` FALSE), the other pumps take over in LIC01. Note the Framo "
                      "behaviour on heartbeat loss (IN-41)."),
         ("Engineer", "Inlet RIO link down: expects the station's level pair invalid "
                      "(`Inlet[i].Input.LevelInsidePen.Status.BadQuality`) and LIC01 continuing on the other pairs."),
         ("Engineer", "Oxy pump drive link down: expects `OxySystem[i].OxyPump.Status.CommunicationOK` FALSE, line "
                      "stops; on return the comm-loss fault is reset automatically."),
         ("Engineer", "Inlet pump trip (Framo): expects Lockdown, the others take its share; Reset after the fix "
                      "(UC-04 alternative)."),
         ("Engineer", "Emergency stop: expects the designed stop of pumps and oxygen (open: IN-14, IN-28, OX-21)."),
         ("Engineer", "Records results; deviations go into the register.")],
   alt=[], exc=[("Unexpected reaction that endangers the fish", [("Engineer", "Stops the test, restores normal "
                                                                              "operation. FINISH (abandoned).")])],
   finish="All tests done and recorded.",
   write=[], read=["Inlet[i].InletPump.Alarm.HeartbeatTimeout", "Inlet[i].InletPump.Status.CommunicationOK",
                   "Inlet[i].InletPump.Status.OxyPermit", "Inlet[i].Input.LevelInsidePen.Status.BadQuality",
                   "OxySystem[i].OxyPump.Status.CommunicationOK"], config=[],
   open=["IN-41, IN-14, IN-28, OX-21, IN-40, OX-34"])

uc(id="UC-10", name="Stop the pen", level="user goal",
   goal="Oxygen off, inlet pumps stopped, outlet as planned.",
   actors=["Commissioning engineer", "Operator"], includes=["UC-00"], extends=[],
   pre=["Pen Starting or Running."], start="The engineer decides to stop.",
   main=[("Engineer", "Pulse `Pen.Command.OxygenStop`: `Pen.Status.OxygenOn` FALSE, lines in auto stop and close."),
         ("Engineer", "Pulse `Pen.Command.Stop`: `Pen.Status.State` -> Stopping (3) -> Stopped (0); pumps in auto "
                      "stop (pumps in manual are NOT stopped: stop them with `Inlet[i].InletPump.Command.Stop`)."),
         ("Engineer", "Checks every `Inlet[i].InletPump.State` Available and every `OxySystem[i].OxyPump.State` not "
                      "running; outlet as planned (the outlet does not close by itself, OUT-01).")],
   alt=[], exc=[], finish="Pen Stopped.",
   write=["Pen.Command.OxygenStop", "Pen.Command.Stop", "Inlet[i].InletPump.Command.Stop"],
   read=["Pen.Status.OxygenOn", "Pen.Status.State", "Inlet[i].InletPump.State", "OxySystem[i].OxyPump.State"],
   config=[], open=["IN-04 (stop accepted only in REMOTE)", "IN-15 (auto outlet close on pump stop)"])

ORDER = ["UC-00", "UC-01", "UC-02", "UC-03", "UC-04", "UC-05", "UC-06", "UC-07", "UC-10", "UC-08", "UC-09"]


# ------------------------------------------------------------------------------------------- check
NODE = re.compile(r"`([A-Za-z_][\w\[\]\.]*)`")


def all_node_refs():
    for u in UC:
        texts = [u["start"], u["finish"]] + u["pre"] + u["open"]
        texts += [t for _, t in u["main"]]
        for _, steps in u["alt"] + u["exc"]:
            texts += [c for _, c in steps]
        texts += [c for c, _ in u["alt"] + u["exc"]]
        for t in texts:
            for m in NODE.finditer(t):
                yield u["id"], m.group(1)
        for key in ("write", "read", "config"):
            for p in u[key]:
                yield u["id"], p


def check(valid):
    bad = []
    for uid, p in all_node_refs():
        n = opc_paths.normalise(p)
        if n not in valid and n + "[i]" not in valid and not any(v.startswith(n + ".") for v in valid):
            bad.append((uid, p))
    return bad


# ------------------------------------------------------------------------------------------- render
ESC = re.compile(r"([\\|\[\]{}*_+^~#-])")


def wtext(t):
    # escape outside code spans, keep node names readable as monospace
    parts = re.split(r"(`[^`]*`)", t)
    out = []
    for p in parts:
        if p.startswith("`") and p.endswith("`"):
            out.append("{{" + ESC.sub(r"\\\1", p[1:-1]) + "}}")
        else:
            out.append(ESC.sub(r"\\\1", p))
    return "".join(out)


def htext(t):
    parts = re.split(r"(`[^`]*`)", t)
    return "".join(f"<code>{html.escape(p[1:-1])}</code>" if p.startswith("`") and p.endswith("`")
                   else html.escape(p) for p in parts)


INTRO = (
    "Use cases for field test and commissioning of the CAS (Heimdall) control system: for each, the OPC UA nodes "
    "to write and to read, in order, with the expected PLC response and the error scenarios. Structured after "
    "J. Cooling, Software Engineering for Real-Time Systems (2020), sec. 3.4.5: use case model (actors, use "
    "cases), text descriptions from START to FINISH, normal scenario, alternatives (errors handled in the "
    "interaction) and exceptions (the goal is abandoned), and include / extend relationships. Node paths are "
    "relative to GVLMain (the only node structure exposed over OPC UA) and checked against the PLC program; "
    "indices are 0-based (Inlet[0] = inlet 1). Node details: page 'CAS OPC UA interface'. Command convention: "
    "pulses (Manual, Auto, Start/Stop of the pen, Reset of an inlet pump, calibrations) are written TRUE and "
    "cleared by the PLC; InletPump / OxyPump Start and Stop are held by the PLC until the state confirms them; "
    "OxyPump Reset and AlarmAck bits are edges the client sets TRUE and then FALSE itself; setpoints are levels.")


def render(source):
    today = dt.date.today().isoformat()
    by = {u["id"]: u for u in UC}
    W, H = [], []
    W.append("{info}Generated " + today + ", nodes checked against " + ESC.sub(r"\\\1", source) +
             ". Do not edit here: change commissioning_usecases.py in workfolder-latex/CAS/OPC UA interface "
             "and regenerate.{info}")
    W.append("{toc:maxLevel=2}")
    W.append("h1. Purpose")
    W.append(wtext(INTRO))
    H.append(f"<p class='gen'>Generated {today}, nodes checked against {html.escape(source)}.</p>")
    H.append("<h1>Purpose</h1><p>" + htext(INTRO) + "</p>")

    W.append("h1. Use case model")
    H.append("<h1>Use case model</h1>")
    W.append("h2. Actors")
    H.append("<h2>Actors</h2><table><tr><th>Actor</th><th>Kind</th><th>Role</th></tr>")
    W.append("|| Actor || Kind || Role ||")
    for a, kind, role in ACTORS:
        W.append(f"| *{wtext(a)}* | {kind} | {wtext(role)} |")
        H.append(f"<tr><td><b>{html.escape(a)}</b></td><td>{kind}</td><td>{htext(role)}</td></tr>")
    H.append("</table>")
    W.append("h2. Use cases, in commissioning order")
    H.append("<h2>Use cases, in commissioning order</h2><table><tr><th>ID</th><th>Use case</th><th>Goal</th>"
             "<th>Level</th><th>Includes</th><th>Extends</th></tr>")
    W.append("|| ID || Use case || Goal || Level || Includes || Extends ||")
    for i in ORDER:
        u = by[i]
        W.append(f"| [{i}|#{i.replace('-', '')}] | *{wtext(u['name'])}* | {wtext(u['goal'])} | {wtext(u['level'])} | "
                 f"{', '.join(u['includes']) or ' '} | {', '.join(u['extends']) or ' '} |")
        H.append(f"<tr><td><a href='#{i.replace('-', '')}'>{i}</a></td><td><b>{html.escape(u['name'])}</b></td>"
                 f"<td>{htext(u['goal'])}</td><td>{html.escape(u['level'])}</td>"
                 f"<td>{', '.join(u['includes'])}</td><td>{', '.join(u['extends'])}</td></tr>")
    H.append("</table>")

    W.append("h1. Use case descriptions")
    H.append("<h1>Use case descriptions</h1>")
    for i in ORDER:
        u = by[i]
        a = i.replace("-", "")
        W.append(f"h2. {{anchor:{a}}}{i} {u['name']}")
        H.append(f"<h2 id='{a}'>{i} {html.escape(u['name'])}</h2>")
        rows = [("Goal", u["goal"]), ("Level", u["level"]), ("Actors", ", ".join(u["actors"])),
                ("Includes", ", ".join(u["includes"]) or "-"), ("Extends", ", ".join(u["extends"]) or "-")]
        W.append("|| " + " || ".join(k for k, _ in rows) + " ||")
        W.append("| " + " | ".join(wtext(v) for _, v in rows) + " |")
        H.append("<table class='meta'><tr>" + "".join(f"<th>{k}</th>" for k, _ in rows) + "</tr><tr>" +
                 "".join(f"<td>{htext(v)}</td>" for _, v in rows) + "</tr></table>")
        W.append("*Preconditions*")
        H.append("<p><b>Preconditions</b></p><ul>")
        for p in u["pre"]:
            W.append("* " + wtext(p))
            H.append("<li>" + htext(p) + "</li>")
        H.append("</ul>")
        W.append("*START:* " + wtext(u["start"]))
        H.append("<p><b>START:</b> " + htext(u["start"]) + "</p>")
        W.append("*Normal scenario*")
        W.append("|| Step || Who || Action, nodes, expected response ||")
        H.append("<p><b>Normal scenario</b></p><table><tr><th>Step</th><th>Who</th><th>Action, nodes, expected "
                 "response</th></tr>")
        for n, (who, t) in enumerate(u["main"], 1):
            W.append(f"| {n} | {wtext(who)} | {wtext(t)} |")
            H.append(f"<tr><td>{n}</td><td>{html.escape(who)}</td><td>{htext(t)}</td></tr>")
        H.append("</table>")
        for title, key in (("Alternatives (errors handled in the interaction)", "alt"),
                           ("Exceptions (goal abandoned)", "exc")):
            if not u[key]:
                continue
            W.append(f"*{title}*")
            H.append(f"<p><b>{title}</b></p><table><tr><th>Condition</th><th>Who</th><th>Action</th></tr>")
            W.append("|| Condition || Who || Action ||")
            for cond, steps in u[key]:
                for who, t in steps:
                    W.append(f"| {wtext(cond)} | {wtext(who)} | {wtext(t)} |")
                    H.append(f"<tr><td>{htext(cond)}</td><td>{html.escape(who)}</td><td>{htext(t)}</td></tr>")
            H.append("</table>")
        W.append("*FINISH:* " + wtext(u["finish"]))
        H.append("<p><b>FINISH:</b> " + htext(u["finish"]) + "</p>")
        if u["write"] or u["read"] or u["config"]:
            W.append("*Nodes*")
            W.append("|| Write (commands, in order) || Settings to check || Monitor ||")
            col = lambda xs: " \\\\ ".join("{{" + ESC.sub(r"\\\1", x) + "}}" for x in xs) or " "
            W.append(f"| {col(u['write'])} | {col(u['config'])} | {col(u['read'])} |")
            colh = lambda xs: "<br>".join(f"<code>{html.escape(x)}</code>" for x in xs)
            H.append("<p><b>Nodes</b></p><table><tr><th>Write (commands, in order)</th><th>Settings to check</th>"
                     f"<th>Monitor</th></tr><tr><td>{colh(u['write'])}</td><td>{colh(u['config'])}</td>"
                     f"<td>{colh(u['read'])}</td></tr></table>")
        if u["open"]:
            W.append("*Open points (register)*")
            H.append("<p><b>Open points (register)</b></p><ul>")
            for o in u["open"]:
                W.append("* " + wtext(o))
                H.append("<li>" + htext(o) + "</li>")
            H.append("</ul>")

    css = ("body{font-family:system-ui,sans-serif;max-width:1200px;margin:24px auto;padding:0 16px;color:#1f2328;"
           "background:#fff}table{border-collapse:collapse;width:100%;margin:6px 0 16px}th,td{border:1px solid #d0d7de;"
           "padding:4px 8px;vertical-align:top;font-size:13px;text-align:left}th{background:#f6f8fa}"
           "code{font-size:12px;background:#f6f8fa;padding:0 3px;border-radius:3px}.gen{color:#57606a}"
           "h2{border-top:1px solid #d0d7de;padding-top:12px}")
    page = ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
            "content='width=device-width,initial-scale=1'><title>CAS commissioning use cases</title>"
            f"<style>{css}</style></head><body><h1>CAS (Heimdall): commissioning use cases</h1>" + "\n".join(H) +
            "</body></html>")
    return "\n".join(W) + "\n", page


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    argv = argv or sys.argv[1:]
    repo = argv[0]
    valid = opc_paths.paths(repo)
    bad = check(valid)
    if bad:
        print(f"{len(bad)} node references not found in GVLMain:")
        for uid, p in bad:
            print(f"  {uid}: {p}")
    import subprocess
    try:
        rev = subprocess.run(["git", "-C", repo, "log", "-1", "--format=%h %cs"], capture_output=True, text=True,
                             check=True).stdout.strip()
    except Exception:   # noqa: BLE001
        rev = "unknown revision"
    wiki, page = render(f"scaleaq/heimdall-plc {rev}")
    open(OUT_WIKI, "w", encoding="utf-8").write(wiki)
    open(OUT_HTML, "w", encoding="utf-8").write(page)
    print(f"{len(UC)} use cases, {sum(1 for _ in all_node_refs())} node references checked; wrote", OUT_WIKI)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
