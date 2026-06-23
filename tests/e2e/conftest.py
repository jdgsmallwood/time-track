"""
Fixtures for Playwright end-to-end tests.

Run all:          pytest tests/e2e/
Run in Firefox:   pytest tests/e2e/ --browser firefox
Run both:         pytest tests/e2e/ --browser chromium --browser firefox
"""
import os
import pytest
from datetime import date, time

# pytest-playwright runs an asyncio event loop internally; Django's async guard
# misdetects this as "called from async context" and raises SynchronousOnlyOperation.
# Setting this env var disables that guard for the test process.
os.environ.setdefault('DJANGO_ALLOW_ASYNC_UNSAFE', 'true')

# ── helpers ───────────────────────────────────────────────────────────────────


def _monday() -> date:
    """Fixed test Monday so URLs are stable."""
    return date(2026, 6, 23)


# ── database fixtures ─────────────────────────────────────────────────────────
# All use transactional_db (not db) because live_server runs in a separate
# thread and needs committed data to be visible.


@pytest.fixture
def test_user(transactional_db):
    from django.contrib.auth import get_user_model
    User = get_user_model()
    return User.objects.create_user(username="e2euser", password="e2epass123")


@pytest.fixture
def plan_week(transactional_db):
    from timetrack.schedule.models import PlanWeek
    return PlanWeek.objects.get_or_create(start_date=_monday())[0]


@pytest.fixture
def plan_week_with_block(plan_week):
    from timetrack.schedule.models import PlanBlock
    block = PlanBlock.objects.create(
        week=plan_week,
        title="Morning run",
        date=_monday(),
        start_time=time(8, 0),
        end_time=time(9, 0),
    )
    return plan_week, block


# ── browser fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def week_url(live_server):
    return f"{live_server.url}/schedule/weeks/{_monday().isoformat()}/"


@pytest.fixture
def authenticated_page(page, live_server, test_user):
    """Browser page pre-authenticated as test_user via the login form."""
    page.goto(f"{live_server.url}/accounts/login/")
    page.fill('[name=username]', "e2euser")
    page.fill('[name=password]', "e2epass123")
    page.click('[type=submit]')
    page.wait_for_load_state("networkidle")
    return page


@pytest.fixture
def week_page(authenticated_page, week_url, plan_week):
    """Authenticated page loaded on the week view with a plan week in the DB."""
    authenticated_page.goto(week_url)
    authenticated_page.wait_for_selector('#week-grid', state='visible')
    authenticated_page.wait_for_function(
        "typeof GRID !== 'undefined' && typeof GRID.updateBlock === 'function'"
    )
    return authenticated_page


@pytest.fixture
def week_page_with_block(authenticated_page, week_url, plan_week_with_block):
    """Authenticated page for block-edit tests: block created first, then page loads."""
    plan_week, block = plan_week_with_block
    authenticated_page.goto(week_url)
    # Wait for the specific block chip to be rendered by grid.js
    authenticated_page.wait_for_selector(f'#block-{block.pk}', state='visible')
    authenticated_page.wait_for_function(
        "typeof GRID !== 'undefined' && typeof GRID.updateBlock === 'function'"
    )
    return authenticated_page, block
