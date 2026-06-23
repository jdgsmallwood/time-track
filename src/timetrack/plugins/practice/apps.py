from django.apps import AppConfig


class PracticeConfig(AppConfig):
    name = "timetrack.plugins.practice"
    label = "plugin_practice"
    verbose_name = "Practice Plugin"

    def ready(self):
        from timetrack.plugins.registry import get_registry
        from .plugin import PracticePlugin

        get_registry().register(PracticePlugin())
