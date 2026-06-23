"""Tests for the plugin registry and the two built-in plugins."""
import pytest

from timetrack.plugins.registry import PluginRegistry, get_registry
from timetrack.plugins.base import TimeTrackPlugin


@pytest.mark.django_db
def test_registry_has_running_and_practice():
    registry = get_registry()
    running = registry.get("running")
    practice = registry.get("practice")
    assert running is not None
    assert practice is not None
    assert running.slug == "running"
    assert practice.slug == "practice"


@pytest.mark.django_db
def test_registry_all_returns_list():
    registry = get_registry()
    plugins = registry.all()
    slugs = [p.slug for p in plugins]
    assert "running" in slugs
    assert "practice" in slugs


@pytest.mark.django_db
def test_registry_choices():
    registry = get_registry()
    choices = registry.choices()
    assert isinstance(choices, list)
    assert all(isinstance(c, tuple) and len(c) == 2 for c in choices)


def test_custom_plugin_registration():
    registry = PluginRegistry()

    class DummyPlugin(TimeTrackPlugin):
        slug = "dummy"
        name = "Dummy"

    plugin = DummyPlugin()
    registry.register(plugin)
    assert registry.get("dummy") is plugin
    assert registry.get("missing") is None


def test_base_plugin_default_methods():
    plugin = TimeTrackPlugin()
    assert plugin.render_panel(None) == ""
    assert plugin.render_summary(None) == ""
    assert plugin.gcal_description(None) == ""
    assert plugin.get_template_form(None) is None
    assert plugin.get_plan_form(None) is None
    # clone_block_data should be a no-op
    plugin.clone_block_data(None, None)
