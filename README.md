# Tenda Camera for Home Assistant

Local Home Assistant integration for Tenda IP cameras.

> **Status: alpha. RP7 V2.0 local authentication, RTSP streams, writable controls, live event polling and a bundled touch-PTZ camera card are working.**
> The first tested device is **Tenda RP7 V2.0** with firmware **V21.7.18.99**.

The integration talks directly to the camera on the LAN using the camera's
local JSON RPC endpoint (`/RPC2`). It does not require TDSEE cloud access.

## Current v0.8.0 scope

The current milestone provides local RP7 V2.0 authentication, device discovery,
two RTSP camera entities and writable configuration switches. All traffic stays
on the LAN; TDSEE cloud access is not required for these functions.

Currently available:

- model, hardware version, firmware and stable device serial;
- main RTSP stream and sub-stream as native Home Assistant camera entities;
- writable motion detection switch;
- writable human detection switch;
- writable human tracking switch;
- writable blind/tamper detection switch;
- ONVIF/RTSP and recording diagnostics;
- manual state refresh and RPC2 re-authentication buttons;
- PTZ direction buttons through the matching Home Assistant ONVIF camera;
- live RPC2 event sensors for motion, person and tamper when the firmware exposes those event codes.

The raw HAR captures used during reverse engineering are **not committed**.
They can contain device identifiers and local network information.

## Installation for development

Copy:

`custom_components/tenda_camera`

to:

`/config/custom_components/tenda_camera`

Restart Home Assistant, then add **Tenda Camera** from
**Settings → Devices & services → Add integration**.

For the RP7 V2.0 web interface the defaults are:

- HTTPS port: `443`
- SSL verification: disabled (the camera uses a self-signed certificate)

## HACS

The repository is structured for HACS. During alpha testing it can be added as
a custom repository. After the integration is stable, validated and released,
it can be submitted for inclusion in the default HACS repository list.

## Roadmap

1. Read-only RPC2 device discovery and diagnostics.
2. Safe writes for motion detection, human filter and human tracking.
3. PTZ and presets.
4. Privacy mode/shutter, IR/night mode, patrol and alarm features.
5. Event/push handling over the camera's local WebSocket interface.
6. Camera/RTSP integration, recording and local/NAS workflows.
7. HACS release and default-store submission.

## Supported devices

| Model | Status |
|---|---|
| Tenda RP7 V2.0 | Initial development target |
| Other Tenda CP/RP models | Not tested yet |

## Disclaimer

This is an independent community project and is not affiliated with Tenda.


## Release model

Development commits are validated by HACS and hassfest. Published versions use
GitHub Releases (for example `v0.2.1`) so HACS can display semantic versions
instead of raw commit hashes and can notify users about normal updates.

During rapid alpha development HACS may cache repository metadata for a while;
manual repository refresh can reveal a release sooner than the periodic refresh.


## PTZ and dashboard controls

Home Assistant's native camera more-info dialog does not provide arbitrary PTZ
overlay controls. v0.4.0 therefore exposes Up/Down/Left/Right as device buttons
when a matching ONVIF camera for the same host is configured.

Those buttons can be placed over the live camera with Home Assistant's built-in
Picture Elements card. A dedicated Tenda Camera card is planned so this can be
installed without hand-written dashboard YAML.

## Detection events

The configuration switches answer a different question from event sensors:

- `Human detection` switch: whether the camera is allowed to detect people.
- `Person detected` binary sensor: whether the camera is reporting a person
  right now.

v0.4.0 probes `eventManager.getEventIndexes` locally every two seconds for
`VideoMotion`, `SmartMotionHuman` and `VideoBlind`. Unsupported event codes
are not exposed as entities.


## Tenda Camera dashboard card

v0.6.0 bundles a Home Assistant custom card with the integration itself, so no
second HACS repository is needed.

The card provides:

- live camera image from the Home Assistant camera proxy;
- a touch PTZ cross directly over the picture;
- press-and-hold movement with Stop on release instead of one large PTZ jump;
- quick Motion / Human detection / Human tracking toggles;
- live Motion and Person indicators over the image.

After updating and restarting Home Assistant, open a dashboard, choose **Add card**
and select **Tenda Camera**. The card tries to select the main Tenda stream
automatically.

Manual fallback:

```yaml
type: custom:tenda-camera-card
entity: camera.your_tenda_main_stream
```

PTZ currently delegates to the already configured Home Assistant ONVIF camera
with the same IP address. Direct Tenda RPC2 PTZ remains a future goal.

## Human detection semantics

There are intentionally two different kinds of entities:

- **Human detection** switch: enables/disables the camera's built-in person
  classification.
- **Human tracking** switch: enables/disables physical pan/tilt tracking after
  the camera has classified a person.
- **Person detected** binary sensor: a live event state used by Home Assistant
  automations.

v0.4.0 polled event indexes without first attaching the RPC2 event manager.
v0.5.0 fixes that by calling `eventManager.attach` before polling
`eventManager.getEventIndexes`, and re-attaches automatically after the camera
session is renewed. Diagnostics now include the raw event responses if a
firmware uses different event codes.


## Stream compatibility in v0.6.0

RP7 V2.0 can encode both streams as H.265. Home Assistant can still extract
fresh preview frames from H.265, while browser live playback may fail. v0.6.0
therefore changes the camera behavior:

- H.264 streams keep native Home Assistant streaming.
- H.265 streams automatically fall back to Home Assistant's MJPEG/still-stream
  path instead of advertising a live mode that the browser cannot play.
- The low-resolution Tenda sub-stream is named **HA compatible stream** and is
  preferred by the bundled Tenda Camera card.
- Main and HA-stream codec selectors expose the camera's real `Encode`
  configuration. Changing a selector mirrors the camera web UI and preserves
  the rest of the encoder table.

For smooth native playback, set **HA stream codec** to **H.264**. The main
stream may remain H.265 if it is wanted for recording/high-quality use.

## Event diagnostics in v0.6.0

The local person/motion event transport is still under reverse engineering.
The integration now exposes a diagnostic entity named **RPC2 event status**
with the attach SID, currently polled codes, values and short raw responses.
This is intentionally diagnostic: it prevents future fixes from guessing
whether the RP7 uses different event codes or a different local event transport.


### v0.6.2 card playback

The bundled card no longer renders `/api/camera_proxy_stream` directly. That
endpoint behaves like an MJPEG proxy and can look like a slideshow. The card
now embeds Home Assistant's native `ha-camera-stream` player, so Home Assistant
can select WebRTC/go2rtc when available and otherwise use its normal HLS path.

For the best browser compatibility use H.264 for the stream shown in Home
Assistant. H.265 is kept as a valid camera setting, but browser playback support
depends on the Home Assistant/player/browser path and is not equivalent to the
native TDSEE app.

Touch PTZ now repeats short ONVIF moves while an arrow is held and sends Stop
when released. This avoids Home Assistant's one-second
`continuous_duration` limit.

### v0.6.2 local events

The previous `getEventIndexes` polling did not prove that RP7 events were
actually being delivered. The integration now also opens the local
Dahua-style `SubscribeNotify.cgi` event stream after
`eventManager.attach` and parses `client.notifyEventStream` messages.
Diagnostics report the stream status and all event codes observed on this
specific firmware.


### v0.6.3 native card wrapper

The bundled Tenda Camera card now mounts Home Assistant's own
`picture-entity` card with `camera_view: live` underneath the PTZ overlay.
This intentionally uses the same live-video implementation that already works
when the camera entity is placed on a normal Home Assistant dashboard.

### v0.6.3 event fallbacks

Live Tenda events are now collected from multiple local sources:

1. Tenda/Dahua-style `SubscribeNotify.cgi` after `eventManager.attach`;
2. matching ONVIF binary-sensor entities from the ONVIF integration configured
   for the same camera IP;
3. legacy `getEventIndexes` only as a final diagnostic fallback.

This is specifically meant to make RP7 V2.0 motion detection useful even when
the proprietary notification transport is firmware-specific.


### v0.7.0 event detection fix

The Motion / Human detection switches are camera configuration values, not
event states. Their Home Assistant states are read back from the RP7
`MotionDetect` config table, so an enabled switch means the camera itself
reported `Enable=true` / `HumanDetectFliter=true`.

Earlier versions could still leave the live event sensors permanently off:
the experimental `SubscribeNotify.cgi` probe treated any HTTP 200 response
as a valid event stream, and that suppressed `eventManager.getEventIndexes`
polling even when no `client.notifyEventStream` message had ever arrived.

v0.7.0 only trusts the push transport after a real event notification and
continues RPC2 snapshot polling otherwise. It also probes the common OEM
aliases for motion/person events once per second.


### v0.8.0 event transport

RP7 V2.0 uses a Dahua-like RPC/config surface. The integration now tries the
camera-family event transport used for live motion alarms directly:

`/cgi-bin/eventManager.cgi?action=attach&codes=[All]`

The connection is long-lived, uses Digest authentication and parses multipart
event frames such as `Code=VideoMotion;action=Start;...`. These events update
the Home Assistant motion/person/tamper binary sensors immediately.

Fallbacks remain active in parallel:

1. camera `eventManager.cgi` multipart stream;
2. OEM `SubscribeNotify.cgi` JSON notification experiment;
3. matching ONVIF binary sensors;
4. RPC2 `eventManager.getEventIndexes` polling.

The diagnostic entity **Event channel / Канал событий** exposes which transport
is actually alive and the last raw event codes seen on this firmware. A simple
HTTP 200 response is not treated as proof that a push channel works; only a real
event frame is.
