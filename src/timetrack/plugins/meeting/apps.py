from django.apps import AppConfig


class MeetingConfig(AppConfig):
    name = "timetrack.plugins.meeting"
    label = "plugin_meeting"
    verbose_name = "Meeting Plugin"

    def ready(self):
        from timetrack.plugins.registry import get_registry
        from .plugin import MeetingPlugin

        get_registry().register(MeetingPlugin())
