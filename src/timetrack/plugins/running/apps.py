from django.apps import AppConfig


class RunningConfig(AppConfig):
    name = "timetrack.plugins.running"
    label = "plugin_running"
    verbose_name = "Running Plugin"

    def ready(self):
        from timetrack.plugins.registry import get_registry
        from .plugin import RunningPlugin

        get_registry().register(RunningPlugin())
