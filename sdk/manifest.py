from sdk.version import get_sdk_metadata


MANIFEST_SECTIONS = [
    "adapters",
    "strategies",
    "skills",
    "enabled_components",
    "version_info",
]


class SDKManifest:
    def __init__(self):
        self._adapters = []
        self._strategies = []
        self._skills = []
        self._enabled_components = []

    def register_adapter(self, name: str) -> None:
        self._adapters.append(name)

    def register_strategy(self, name: str) -> None:
        self._strategies.append(name)

    def register_skill(self, name: str) -> None:
        self._skills.append(name)

    def register_enabled(self, component: str) -> None:
        self._enabled_components.append(component)

    def generate(self) -> dict:
        meta = get_sdk_metadata()
        return {
            "sdk_version": meta["version"],
            "runtime_version": meta["runtime"],
            "build_timestamp": meta["build"],
            "installed_adapters": self._adapters,
            "installed_strategies": self._strategies,
            "installed_skills": self._skills,
            "enabled_components": self._enabled_components,
        }
