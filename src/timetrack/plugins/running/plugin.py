from timetrack.plugins.base import TimeTrackPlugin

from .forms import RunSessionForm
from .models import RunSession


class RunningPlugin(TimeTrackPlugin):
    slug = "running"
    name = "Running"
    icon = "🏃"
    color = "#22c55e"

    def clone_block_data(self, template_block, plan_block) -> None:
        try:
            src = template_block.run_session
        except RunSession.DoesNotExist:
            return
        RunSession.objects.create(
            plan_block=plan_block,
            run_type=src.run_type,
            planned_km=src.planned_km,
            planned_pace=src.planned_pace,
        )

    def clone_plan_block_data(self, src_plan_block, dest_plan_block) -> None:
        src = self._get_session(src_plan_block)
        if not src:
            return
        RunSession.objects.create(
            plan_block=dest_plan_block,
            run_type=src.run_type,
            planned_km=src.planned_km,
            planned_pace=src.planned_pace,
        )

    def init_block_data(self, plan_block) -> None:
        RunSession.objects.get_or_create(plan_block=plan_block, defaults={"run_type": "base"})

    def get_template_form(self, template_block, data=None):
        instance = RunSession.objects.filter(template_block=template_block).first()
        return RunSessionForm(data, instance=instance, prefix="run")

    def get_plan_form(self, plan_block, data=None):
        instance = RunSession.objects.filter(plan_block=plan_block).first()
        return RunSessionForm(data, instance=instance, prefix="run")

    def render_summary(self, block) -> str:
        session = self._get_session(block)
        if not session:
            return ""
        km = session.planned_km or "?"
        return f'<span class="text-xs font-medium">{session.get_run_type_display()} · {km} km</span>'

    def gcal_description(self, plan_block) -> str:
        session = self._get_session(plan_block)
        if not session:
            return ""
        parts = [session.get_run_type_display()]
        if session.planned_km:
            parts.append(f"{session.planned_km} km")
        if session.planned_pace:
            parts.append(f"@ {session.planned_pace}")
        return " · ".join(parts)

    def _get_session(self, block):
        attr = "run_session"
        try:
            return getattr(block, attr, None)
        except RunSession.DoesNotExist:
            return None
