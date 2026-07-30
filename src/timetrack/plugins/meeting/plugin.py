from timetrack.plugins.base import TimeTrackPlugin

from .forms import MeetingNotesForm
from .models import MeetingNotes


class MeetingPlugin(TimeTrackPlugin):
    slug = "meeting"
    name = "Meeting"
    icon = "📝"
    color = "#0ea5e9"

    # clone_block_data / clone_plan_block_data stay no-ops: minutes never copy forward.
    # gcal_description stays empty: minutes are private to TimeTrack.

    def init_block_data(self, plan_block) -> None:
        MeetingNotes.objects.get_or_create(plan_block=plan_block)

    def get_plan_form(self, plan_block, data=None):
        instance = MeetingNotes.objects.filter(plan_block=plan_block).first()
        return MeetingNotesForm(data, instance=instance, prefix="meeting")

    def render_summary(self, block) -> str:
        notes = self._get_notes(block)
        if not notes or not notes.minutes.strip():
            return ""
        return '<span class="text-xs font-medium">📝 Minutes</span>'

    def _get_notes(self, block):
        try:
            return getattr(block, "meeting_notes", None)
        except MeetingNotes.DoesNotExist:
            return None
