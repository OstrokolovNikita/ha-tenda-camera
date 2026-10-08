# Changelog

## v0.7.0

- Fix the core RP7 event bug: an HTTP 200 from the experimental SubscribeNotify endpoint was previously treated as a healthy push stream even when no event had ever arrived. That incorrectly disabled RPC2 event-index polling and left motion/person sensors permanently off.
- Only mark the push transport as working after a real `client.notifyEventStream` message is received.
- Keep RPC2 event-index polling active unless a specific sensor has a proven push/ONVIF source.
- Poll RP7 event indexes every second so short motion/person states are less likely to be missed.
- Probe multiple Dahua/Tenda OEM aliases for motion and person events: `VideoMotion`, `VideoMotionInfo`, `MDResult`, `MoveDetection`, `SmartMotionHuman`, `HumanDetection`, `HumanTrait`, plus tamper aliases.
- Do not permanently blacklist an event code after one RPC refusal; retry it on later cycles.
- Add camera readback for `MotionDetect.Enable`, `HumanDetectFliter`, `HumanTrack` and sensitivity to the RPC2 event-status diagnostics, proving whether the switches are actually enabled on the camera.

## v0.6.9

- Fit fullscreen video by screen height instead of screen width.
- Preserve the complete 16:9 camera frame on 20:9/21:9 phones, leaving black side bars when necessary instead of cropping vertically.
- Add two-finger pinch zoom in fullscreen mode, from 1x to 5x.
- Zoom affects only the video layer; PTZ and close controls stay fixed and usable.
- Reset zoom whenever fullscreen is opened, closed, or rebuilt after an orientation/viewport change.

## v0.6.8

- Stop relying on Android auto-rotate for camera fullscreen.
- Render fullscreen inside a dedicated landscape stage and rotate that stage in CSS whenever the phone viewport remains portrait.
- Recalculate the landscape stage from the actual current viewport bounds on every fullscreen/orientation/resize change.
- Force the embedded Home Assistant camera card, hui-image container, camera stream and underlying video player to fill the fullscreen stage edge-to-edge.
- Use cover mode for the main stream so there are no large unused white/black fields; the image may be cropped slightly on screens wider than 16:9.
- Keep PTZ controls inside the same rotated landscape stage so their position follows the video.

## v0.6.7

- On mobile, fullscreen now requests landscape orientation after entering browser/WebView fullscreen.
- Rebuild the fullscreen main-stream card after the orientation transition so it uses the final landscape viewport ratio.
- Use `cover` for the fullscreen main stream and match the picture-card aspect ratio to the landscape viewport.
- Force the fullscreen overlay and embedded camera card to occupy the entire viewport with a black background, removing the large white fields.
- Recalculate the fullscreen layout on orientation/viewport changes and unlock orientation when fullscreen closes.

## v0.6.6

- Make the dashboard stream deterministic: the normal Tenda Camera card always uses the RP7 sub-stream, while fullscreen always opens the main stream.
- Register the bundled card as a real Lovelace module resource in storage mode instead of relying only on dynamic frontend-module injection.
- Keep the previous frontend extra-module registration only as a YAML-mode fallback.
- This specifically fixes Companion App/mobile clients showing `Custom element doesn't exist: tenda-camera-card`.
- Bump the card URL on every release so browser and mobile WebView caches receive the new JavaScript.

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
