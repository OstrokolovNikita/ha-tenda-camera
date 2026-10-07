# Changelog

## v0.3.0

- Fix unavailable RP7 motion/human state by normalizing config table shapes.
- Replace the old read-only configuration binary sensors with real writable switches.
- Add motion detection, human detection, human tracking and tamper-detection controls.
- Add native Home Assistant camera entities for the RP7 main and sub RTSP streams.
- Add refresh and RPC2 re-authentication utility buttons.
- Remove legacy v0.2.x binary-sensor registry entries during migration.
- Keep read-modify-write operations safe by preserving the complete camera config table.

## v0.2.1

- Fix RP7 authentication sessions when the camera is addressed by IP.
- Use an IP-compatible aiohttp cookie jar.
- Keep the RP7 HTTPS connection alive like the camera web UI.
- RP7 V2.0 now connects successfully and exposes device metadata and read-only
  configuration entities in Home Assistant.

## v0.2.0

- Add local RP7 `global.login` authentication.
- Add username and password fields to the Home Assistant config flow.
- Add automatic re-authentication.
- Redact the camera password from diagnostics.

## v0.1.x

- Initial RPC2 client and connection diagnostics.
- Read device/model/firmware information.
- Read MotionDetect, BlindDetect, RecordMode, ONVIF and RTSP configuration.
