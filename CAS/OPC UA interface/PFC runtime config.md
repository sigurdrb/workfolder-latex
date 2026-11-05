# PFC runtime config (OPC UA server)

Settings for the CODESYS runtime on the CAS PFC200. They are not in the CODESYS project, so a new PFC
or a firmware reset needs them added by hand.

File on the PFC: `/etc/codesys3.d/CODESYSControl_User.cfg`. Backup next to it: `CODESYSControl_User.cfg.bak`.

## Added 2026-11-05

At the end of the file:

```ini
[CmpOPCUAServer]
SessionTimeout=60000
ItemMinSamplingRate=500
SchedulerResolution=50
```

| Setting | What it does | Why |
|---|---|---|
| `SessionTimeout=60000` | A dead client's session is dropped after 60 s | Clean up after the HMI or UaExpert disappears |
| `ItemMinSamplingRate=500` | The server never samples faster than 500 ms, whatever a client asks | Limit CPU. The HMI uses 1 s; 500 keeps the HMI wave view usable |
| `SchedulerResolution=50` | The OPC UA scheduler ticks every 50 ms | Fewer wake-ups, less CPU |

Not used, from the same forum tip: `TraceLevel=1023` (trace logging, costs CPU), large stack buffers,
fixed worker pool, thread priority. Add them only if needed.

These settings affect the PLC's OPC UA server (HMI, SiteControl, UaExpert). They do not affect the PLC as a
client to the Framo servers (Data Sources Framo_1..3).

## Already in the file

`[CmpSecureChannel]` (certificate) and `[CmpUserMgr]`: anonymous login allowed, user management not
enforced, password policy off. Fine during commissioning; close before handover.

## How to change

1. `cp /etc/codesys3.d/CODESYSControl_User.cfg /etc/codesys3.d/CODESYSControl_User.cfg.bak`
2. `nano /etc/codesys3.d/CODESYSControl_User.cfg`, add or change lines, `Ctrl+O` Enter, `Ctrl+X`.
3. Reboot the PFC. The pumps run on the link-loss setpoint while it starts.
4. Update this file.
