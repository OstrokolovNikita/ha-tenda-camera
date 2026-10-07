from __future__ import annotations

from datetime import timedelta

DOMAIN = "tenda_camera"

CONF_PORT = "port"
CONF_VERIFY_SSL = "verify_ssl"

DEFAULT_PORT = 443
DEFAULT_VERIFY_SSL = False
DEFAULT_SCAN_INTERVAL = timedelta(seconds=30)

RPC_PATH = "/RPC2"

CONFIG_GENERAL = "General"
CONFIG_DEVICE_NAME = "DeviceName"
CONFIG_MOTION = "MotionDetect"
CONFIG_BLIND = "BlindDetect"
CONFIG_RECORD_MODE = "RecordMode"
CONFIG_SECURITY = "Security"
