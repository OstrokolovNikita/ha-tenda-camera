# Tenda Camera for Home Assistant

Local Home Assistant integration for Tenda IP cameras.

> **Status: early alpha / read-only probe.**
> The first tested device is **Tenda RP7 V2.0** with firmware **V21.7.18.99**.

The integration talks directly to the camera on the LAN using the camera's
local JSON RPC endpoint (`/RPC2`). It does not require TDSEE cloud access.

## Current v0.1 scope

The first milestone is deliberately read-only. It validates the local RPC API
and exposes the camera's configuration state in Home Assistant without changing
camera settings.

Currently read:

- model, hardware version, firmware and stable device serial;
- motion detection enabled state;
- human detection filter enabled state;
- human tracking enabled state;
- blind/tamper detection enabled state;
- ONVIF enabled state;
- RTSP enabled state;
- record mode.

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
