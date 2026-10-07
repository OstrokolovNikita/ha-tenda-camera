# Changelog

## v0.6.5

- Remove the custom stream-name badge from the dashboard card.
- Mirror the PTZ cross to the left side of the camera image.
- Move the fullscreen control to the bottom-right corner like a normal video control.
- Fullscreen still opens the main Tenda stream, not the lighter dashboard stream.
- Keep PTZ available in fullscreen.
- Move live event badges away from the PTZ cluster.

## v0.6.4

- Remove the stream-name badge from the bundled Tenda Camera card.
- Add a fullscreen button directly over the preview.
- Fullscreen mode always opens the Tenda main stream for maximum configured quality, while the normal card can keep using the lighter stream.
- Keep PTZ controls available in fullscreen mode.
- Use the browser Fullscreen API when available, with a full-viewport overlay fallback.

## v0.6.3

- Rebuild the custom Tenda Camera card around Home Assistant's own native `picture-entity` live card instead of embedding `ha-camera-stream` directly inside the integration shadow DOM.
- This makes the card use the exact same live-video path as a normal Home Assistant camera card, while keeping the Tenda PTZ overlay on top.
- Mirror matching ONVIF event entities from the already configured ONVIF camera on the same IP (for example `Cell Motion Detection`) into the Tenda event sensors.
- Keep local SubscribeNotify event listening in parallel for Tenda/Dahua-style motion, human and tamper notifications.
- Keep event sensors stable at their last known boolean value instead of flipping to Unknown when an experimental event transport returns no value.
- Add ONVIF mirror sources to diagnostics.

## v0.6.2

- Replace the custom card's MJPEG proxy image with Home Assistant's native `ha-camera-stream` player, allowing WebRTC/go2rtc or HLS instead of slideshow-style proxy frames.
- Fix the card PTZ error caused by invalid ONVIF `continuous_duration=10`.
- Change touch PTZ to repeated short pulses while the arrow is held and Stop on release.
- Clamp every PTZ duration to Home Assistant's ONVIF maximum of one second.
- Prefer an H.264 main stream when creating a new Tenda Camera card.
- Keep camera STREAM capability stable when codecs are changed at runtime.
- Add an experimental local `SubscribeNotify.cgi` event listener after `eventManager.attach`.
- Parse `client.notifyEventStream` locally for motion, person and tamper events, including Human object classification inside generic motion events.
- Keep old event-index polling only as a fallback and expose notification stream diagnostics.

## v0.6.1

- Fix startup failure introduced in v0.6.0 on Home Assistant installations where the internal camera helper import is unavailable.
- Decode RTSP still frames directly through the camera stream object instead of importing an internal helper.
- Treat optional Encode/event probing as non-fatal so unsupported firmware behavior cannot take the whole Tenda entry down.

## v0.6.0

- Fix the camera entity fallback path so H.265 streams no longer expose a broken browser live mode.
- Add RTSP snapshot decoding for Home Assistant MJPEG fallback.
- Keep native Home Assistant streaming automatically when the selected camera stream uses H.264.
- Rename the sub-stream to `HA compatible stream` and prefer it in the bundled Tenda Camera card.
- Add writable `Main stream codec` and `HA stream codec` selectors for H.264/H.265.
- Mirror the RP7 web UI's Encode table update, including H.264 Main / H.265 Baseline profile values.
- Add `RPC2 event status` diagnostic entity with attach SID, event values and short raw responses.
- Do not claim person/motion event handling is solved until RP7 V2.0 raw responses confirm the local event code/transport.

## v0.5.0

- Fix live motion/person/tamper sensors by attaching the RPC2 event manager before reading event indexes.
- Re-attach the event manager automatically after RP7 authentication/session renewal.
- Include raw event polling details in Home Assistant diagnostics for model-specific troubleshooting.
- Add a bundled `Tenda Camera` Lovelace card loaded automatically by the integration.
- Put a touch PTZ cross directly over the camera image.
- Use press-and-hold PTZ movement and Stop on release for much smoother control.
- Add Motion, Human detection and Human tracking controls to the camera card.
- Add live Motion and Person indicators on the camera card.
- Reduce the movement of the standalone one-shot PTZ buttons.
- Add integration services used by the camera card for PTZ and feature control.

## v0.4.0

- Add live motion/person/tamper event probing over local RPC2.
- Add `Person detected` as a real event binary sensor when supported by RP7 firmware.
- Poll event state separately every two seconds without increasing the slower settings poll.
- Add Up/Down/Left/Right PTZ buttons.
- PTZ buttons delegate to Home Assistant's existing ONVIF camera configured for the same IP.
- Document the difference between detection enable switches and live detection events.

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
