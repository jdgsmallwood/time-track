from django.apps import AppConfig


class PluginsConfig(AppConfig):
    name = "timetrack.plugins"
    label = "plugins"

    def ready(self):
        # Registry is populated by each plugin's AppConfig.ready()
        pass
