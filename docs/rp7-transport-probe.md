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

## Installation and version channels via HACS

- **Stable:** `v0.8.1`, normal GitHub release, source from `main`.
- **Test:** `v0.8.3b1`, GitHub **Pre-release**, source from this diagnostic branch.
- Rejected `v0.8.2` is marked **Pre-release**, not the stable update.
- There is no file copying and no ZIP installation. All versions are published
  through GitHub Releases for HACS.
- To opt into experimental builds, enable the (usually disabled) HACS switch
  entity for Tenda Camera that includes pre-release updates. Download/update
  the offered `v0.8.3b1` using HACS. HACS does not automatically install the
  test build just because its release exists.
- After Home Assistant restarts, open Developer Tools → States →
  `sensor.rp7v2_0_rpc2_event_status` and copy only the **`transport_probe`**
  attribute. Allow up to 15 seconds for first result.
- If WebSocket says connected, trigger a motion event and check the
  `ws_messages` count again within 90 seconds.

To return to stable, reinstall `v0.8.1` through HACS and disable its beta
switch; restart Home Assistant. No file operations.

## What results mean
- `tcp_9002: open`: a TCP connection was possible (not proof of WS/event).
- `ws_root_9002: connected_ws`: WS handshake succeeded on the root path.
- `ws_messages > 0`: at least one incoming WS frame was observed.
- `ws_root_9002: ws:HTTP_404 | wss:...`: root-path handshake unsuccessful.
- `tcp_8000: open`: proprietary port accepts TCP, protocol remains unknown.

Rollback: reinstall the published stable v0.8.1 from HACS and restart HA.
This is a diagnostic build, **not** a fix for binary sensors.
