"""Migration guard — raises if caller tries to bypass compat boundary."""


class MigrationGuard:
    _registered: dict = {}

    @classmethod
    def register(cls, phase: str, module: str) -> None:
        cls._registered[module] = phase

    @classmethod
    def assert_phase(cls, expected: str, module: str) -> None:
        actual = cls._registered.get(module, expected)
        if actual != expected:
            raise RuntimeError(
                f"Migration guard: {module!r} registered for phase {actual!r}, "
                f"called from {expected!r}"
            )
