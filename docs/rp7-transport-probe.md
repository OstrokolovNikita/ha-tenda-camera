# RP7 V2.0 — local event transport diagnostics (experimental)

Base: v0.8.1 (`29bc130c27953711d2356b3ab30cef7e17c799cf`).
This branch **does not implement or claim working motion/person events**.
It does not change the card, streams, PTZ, fullscreen or motion switches.

## What is probed
- TCP connect on 9002 and 8000, without sending application data.
- An unauthenticated, cookie-free WebSocket handshake against `/` on port 9002
  (first `ws://`, then `wss://`), followed by up to 90 seconds of listening
  if successful.
- A failed handshake to `/` **does not prove that WebSocket is unavailable**:
  the camera may use another URL, authentication or a proprietary protocol.
- No session cookies, passwords, authentication headers, event subscription
  commands or RTSP requests are sent by the probe.
- Never records complete message contents, URLs with secrets or binary dumps.
  For incoming WS frames it keeps message count, kind, length, safe JSON key
  names and a few allowlisted method/event labels.

## Install without changing stable GitHub main or creating a HACS release
Download this branch as a ZIP, extract it, copy **only**
`custom_components/tenda_camera` over the existing Home Assistant
`/config/custom_components/tenda_camera`, and restart Home Assistant.

Open Developer Tools → States → `sensor.rp7v2_0_rpc2_event_status` and copy
the **`transport_probe`** attribute. Allow up to 15 seconds for first result.
If `ws_root_9002` says connected, trigger one ordinary motion event in view
of the camera and check `ws_messages` again within 90 seconds.

Please redact any account, URL tokens and identifiers if pasting other
attributes. Do not share raw HAR or captured authentication frames.

## What results mean
- `tcp_9002: open`: a TCP connection was possible (not proof of WS/event).
- `ws_root_9002: connected_ws`: WS handshake succeeded on the root path.
- `ws_messages > 0`: at least one incoming WS frame was observed.
- `ws_root_9002: ws:HTTP_404 | wss:...`: root-path handshake unsuccessful.
- `tcp_8000: open`: proprietary port accepts TCP, protocol remains unknown.

Rollback: reinstall the published stable v0.8.1 from HACS and restart HA.
This is a diagnostic build, **not** a fix for binary sensors.
