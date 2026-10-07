# RP7 V2.0 protocol notes

These notes contain only sanitized facts discovered from the local camera API.

## Local endpoints

- HTTPS web/RPC: `443`
- JSON RPC endpoint: `/RPC2`
- WebSocket port advertised by RPC: `9002`
- RTSP: `554`
- Service port: `8000`

## Confirmed read methods

- `magicBox.getProductDefinition`
- `magicBox.getDynamicInfo`
- `global.getCurrentTime`
- `configManager.getConfig`
- `configManager.getIfCaps`
- `configManager.getRTSPCaps`
- `encode.getConfigCaps`

## Confirmed config tables

- `General`
- `DeviceName`
- `Security`
- `MotionDetect`
- `BlindDetect`
- `RecordMode`
- `Encode`
- `VideoInOptions`
- `Network`
- `RTSPWeb`
- `PortCfg`
- `AutoMaintain`

The RP7 V2.0 `MotionDetect` table exposes:

- `Enable`
- `HumanDetectFliter` (spelling used by the device)
- `HumanTrack`
- `Level`
- `Region`

Raw captures are intentionally excluded from the repository.
