class TimeTrackPlugin:
    """
    Base class for TimeTrack plugins.

    Each plugin is a self-contained Django app that implements this interface and
    registers itself via the plugin registry in its AppConfig.ready().
    """

    slug: str = ""
    name: str = ""
    icon: str = "📌"
    color: str = "#6366f1"

    def clone_block_data(self, template_block, plan_block) -> None:
        """Copy plugin-specific data from a TemplateBlock to a new PlanBlock."""

    def clone_plan_block_data(self, src_plan_block, dest_plan_block) -> None:
        """Copy plugin-specific data from one PlanBlock to another (used by copy-forward)."""

    def get_template_form(self, template_block, data=None):
        """Return a bound or unbound ModelForm for plugin data on a TemplateBlock."""
        return None

    def get_plan_form(self, plan_block, data=None):
        """Return a bound or unbound ModelForm for plugin data on a PlanBlock."""
        return None

    def render_panel(self, block) -> str:
        """Return HTML string for the detailed editor panel."""
        return ""

    def render_summary(self, block) -> str:
        """Return a short HTML string for display on the week grid chip."""
        return ""

    def gcal_description(self, plan_block) -> str:
        """Return extra text to append to the Google Calendar event description."""
        return ""

    def init_block_data(self, plan_block) -> None:
        """Create default plugin data for a newly created plan block.

        Called when a block is created with plugin_slug set but without
        drag-from-chip data. Use get_or_create so this is safe to call twice.
        """

    def get_suggestions(self, plan_week) -> list:
        """Return draggable suggestion chips for the week view 'To Schedule' panel.

        Each dict must include: title, duration_minutes, color, scheduled_count,
        recurrence_count, plugin_slug, and practice_goal_id (or similar ID key).
        """
        return []
