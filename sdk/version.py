from datetime import datetime, timezone

SDK_NAME = "trading-intelligence-sdk"
SDK_VERSION = "4.10.0"
SDK_BUILD = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def sdk_version() -> str:
    return SDK_VERSION


def runtime_version() -> str:
    return f"{SDK_NAME}/{SDK_VERSION}"


def get_sdk_metadata() -> dict:
    return {
        "name": SDK_NAME,
        "version": SDK_VERSION,
        "build": SDK_BUILD,
        "runtime": runtime_version(),
    }
