# Tenda Camera for Home Assistant

Local Home Assistant integration for Tenda IP cameras.

> **Status: alpha. RP7 V2.0 local authentication, RTSP streams, writable controls, PTZ buttons and live event probing are working.**
> The first tested device is **Tenda RP7 V2.0** with firmware **V21.7.18.99**.

The integration talks directly to the camera on the LAN using the camera's
local JSON RPC endpoint (`/RPC2`). It does not require TDSEE cloud access.

## Current v0.4.0 scope

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
