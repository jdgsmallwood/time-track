from timetrack.plugins.base import TimeTrackPlugin

from .forms import PracticeSessionForm
from .models import PracticeSession


class PracticePlugin(TimeTrackPlugin):
    slug = "practice"
    name = "Instrument Practice"
    icon = "🎵"
    color = "#a855f7"

    def clone_block_data(self, template_block, plan_block) -> None:
        try:
            src = template_block.practice_session
        except PracticeSession.DoesNotExist:
            return
        PracticeSession.objects.create(
            plan_block=plan_block,
            goal=src.goal,
            instrument=src.instrument,
            focus=src.focus,
            pieces=src.pieces,
            planned_minutes=src.planned_minutes,
        )

    def clone_plan_block_data(self, src_plan_block, dest_plan_block) -> None:
        src = self._get_session(src_plan_block)
        if not src:
            return
        PracticeSession.objects.create(
            plan_block=dest_plan_block,
            goal=src.goal,
            instrument=src.instrument,
            focus=src.focus,
            pieces=src.pieces,
            planned_minutes=src.planned_minutes,
        )

    def get_template_form(self, template_block, data=None):
        instance = PracticeSession.objects.filter(template_block=template_block).first()
        return PracticeSessionForm(data, instance=instance, prefix="practice")

    def get_plan_form(self, plan_block, data=None):
        instance = PracticeSession.objects.filter(plan_block=plan_block).first()
        return PracticeSessionForm(data, instance=instance, prefix="practice")

    def render_summary(self, block) -> str:
        session = self._get_session(block)
        if not session:
            return ""
        label = session.instrument or "Practice"
        return f'<span class="text-xs font-medium">{label} · {session.get_focus_display()}</span>'

    def gcal_description(self, plan_block) -> str:
        session = self._get_session(plan_block)
        if not session:
            return ""
        parts = []
        if session.instrument:
            parts.append(session.instrument)
        parts.append(session.get_focus_display())
        if session.planned_minutes:
            parts.append(f"{session.planned_minutes} min")
        if session.pieces:
            parts.append(session.pieces)
        return " · ".join(parts)

    def get_suggestions(self, plan_week) -> list:
        from django.db.models import Count, Q
        from .models import PracticeGoal

        goals = (
            PracticeGoal.objects
            .filter(is_active=True)
            .annotate(
                scheduled_count=Count(
                    "sessions",
                    filter=Q(sessions__plan_block__week=plan_week) if plan_week else Q(pk__isnull=True),
                )
            )
        )
        return [
            {
                "pk": g.pk,
                "title": g.title,
                "duration_minutes": g.duration_minutes,
                "color": g.color,
                "scheduled_count": g.scheduled_count,
                "recurrence_count": g.recurrence_count,
                "plugin_slug": self.slug,
                "practice_goal_id": g.pk,
            }
            for g in goals
        ]

    def _get_session(self, block):
        try:
            return getattr(block, "practice_session", None)
        except PracticeSession.DoesNotExist:
            return None
