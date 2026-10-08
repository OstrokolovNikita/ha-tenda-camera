# RP7 V2.0 test v0.8.3b4 — collecting a local event journal

Experimental ONLY. Stable release remains **v0.8.1** (not changed).

## Install

1. In HACS, enable pre-releases for Tenda Camera if they are not already enabled.
2. Update Tenda Camera to `v0.8.3b4 TEST` through HACS.
3. Restart Home Assistant; keep it running while waiting for TDSEE alarm activity.

No ZIPs, manual file copying, command line or configuration changes.

## What to do when TDSEE reports a motion/person alarm

1. Note the **date and exact local time** of the alarm shown in TDSEE and
   whether it was a motion or person alarm. A push notification is not
   necessary; a history entry is sufficient.
2. In Home Assistant: Settings → Devices & Services →
   **Tenda Camera** integration → three-dot menu → **Download diagnostics**.
3. The downloaded JSON includes `event_trace.records` with UTC timestamps.
   Send the trace section or the downloaded diagnostics JSON after reviewing
   it for any information you do not want to share.
4. It is also useful to download the file *before* any TDSEE alarm, as a
   baseline, and once again after an alarm.

The journal stores only safe metadata, not raw HTTP requests, image/video
frames, passwords, cloud messages, full WebSocket payloads or credentials.

## Important limitations

- The existing WebSocket connection on 9002 is unauthenticated and passive;
  if the camera requires an explicit subscription, events may never arrive.
- Port 8000 is checked for TCP reachability but no proprietary protocol
  commands are sent to it.
- TDSEE cloud alarm messages are not captured; you must provide their time
  separately for correlation.
- The journal does not turn on the motion/person binary sensors by itself.
- A quiet log **does not prove** the camera failed to detect movement.
- Trace files are private HA storage and automatically rotate, 512 KiB each,
  retaining up to approximately 1 MiB; diagnostics export the newest 800
  records. Oldest records can be overwritten during extended monitoring.

## Rolling back

Install the stable `v0.8.1` through HACS and restart HA; turn off
pre-releases if desired. No manual file operations.
