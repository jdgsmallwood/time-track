from .base import TimeTrackPlugin


class PluginRegistry:
    def __init__(self):
        self._plugins: dict[str, TimeTrackPlugin] = {}

    def register(self, plugin: TimeTrackPlugin) -> None:
        self._plugins[plugin.slug] = plugin

    def get(self, slug: str) -> TimeTrackPlugin | None:
        return self._plugins.get(slug)

    def all(self) -> list[TimeTrackPlugin]:
        return list(self._plugins.values())

    def choices(self) -> list[tuple[str, str]]:
        return [(p.slug, p.name) for p in self._plugins.values()]


_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    return _registry
