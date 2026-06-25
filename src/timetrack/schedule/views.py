import json
from datetime import date, timedelta

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from timetrack.plugins.registry import get_registry

from .forms import CloneTemplateForm, PlanBlockForm, TemplateBlockForm, TemplateWeekForm, WeeklyTaskForm
from .models import PlanBlock, PlanWeek, TemplateBlock, TemplateWeek, WeeklyTask
from .services import clone_template_to_week, iso_week_monday, week_monday, week_stats


# ─── Template Weeks ──────────────────────────────────────────────────────────

class TemplateWeekListView(View):
    def get(self, request):
        templates = TemplateWeek.objects.prefetch_related("blocks").all()
        form = TemplateWeekForm()
        return render(request, "schedule/template_list.html", {"templates": templates, "form": form})

    def post(self, request):
        form = TemplateWeekForm(request.POST)
        if form.is_valid():
            tw = form.save()
            if request.headers.get("HX-Request"):
                return render(request, "schedule/partials/template_card.html", {"template": tw})
        templates = TemplateWeek.objects.all()
        return render(request, "schedule/template_list.html", {"templates": templates, "form": form})


class TemplateWeekDetailView(View):
    def get(self, request, pk):
        from timetrack.core.models import Category

        template = get_object_or_404(TemplateWeek, pk=pk)
        blocks = template.blocks.select_related("category").all()
        form = TemplateWeekForm(instance=template)
        registry = get_registry()
        grid_data = _blocks_to_grid(blocks, date_field=False)
        return render(
            request,
            "schedule/template_editor.html",
            {
                "template": template,
                "form": form,
                "grid_data": json.dumps(grid_data),
                "plugins": registry.all(),
                "block_form": TemplateBlockForm(),
                "categories": Category.objects.all(),
                "day_names": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
            },
        )

    def post(self, request, pk):
        template = get_object_or_404(TemplateWeek, pk=pk)
        form = TemplateWeekForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
        if request.headers.get("HX-Request"):
            return HttpResponse(status=204)
        return redirect("template-detail", pk=pk)

    def delete(self, request, pk):
        TemplateWeek.objects.filter(pk=pk).delete()
        return redirect("templates")


# ─── Template Blocks ─────────────────────────────────────────────────────────

class TemplateBlockCreateView(View):
    def post(self, request, template_pk):
        template = get_object_or_404(TemplateWeek, pk=template_pk)
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
        form = TemplateBlockForm(data)
        if form.is_valid():
            block = form.save(commit=False)
            block.template = template
            block.save()
            registry = get_registry()
            plugin = registry.get(block.plugin_slug) if block.plugin_slug else None
            return render(
                request,
                "schedule/partials/block_chip.html",
                {"block": block, "plugin": plugin, "is_template": True},
            )
        return JsonResponse({"errors": form.errors}, status=400)


class TemplateBlockUpdateView(View):
    def get(self, request, pk):
        from timetrack.core.models import Category

        block = get_object_or_404(TemplateBlock, pk=pk)
        form = TemplateBlockForm(instance=block)
        registry = get_registry()
        plugin = registry.get(block.plugin_slug) if block.plugin_slug else None
        plugin_form = plugin.get_template_form(block) if plugin else None
        return render(
            request,
            "schedule/partials/block_edit_panel.html",
            {
                "block": block, "form": form, "plugin_form": plugin_form,
                "is_template": True, "categories": Category.objects.all(),
            },
        )

    def post(self, request, pk):
        block = get_object_or_404(TemplateBlock, pk=pk)
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
        form = TemplateBlockForm(data, instance=block)
        if form.is_valid():
            block = form.save()
            registry = get_registry()
            plugin = registry.get(block.plugin_slug) if block.plugin_slug else None
            if plugin:
                plugin_form = plugin.get_template_form(block, data)
                if plugin_form and plugin_form.is_valid():
                    session = plugin_form.save(commit=False)
                    if session.pk is None:
                        session.template_block = block
                    session.save()
            return render(
                request,
                "schedule/partials/block_chip.html",
                {"block": block, "plugin": plugin, "is_template": True},
            )
        return JsonResponse({"errors": form.errors}, status=400)

    def patch(self, request, pk):
        """Handle drag/resize updates (JSON body with time/day fields)."""
        block = get_object_or_404(TemplateBlock, pk=pk)
        body = json.loads(request.body)
        for field in ("start_time", "end_time", "day_of_week"):
            if field in body:
                setattr(block, field, body[field])
        block.save()
        registry = get_registry()
        plugin = registry.get(block.plugin_slug) if block.plugin_slug else None
        return render(
            request,
            "schedule/partials/block_chip.html",
            {"block": block, "plugin": plugin, "is_template": True},
        )

    def delete(self, request, pk):
        TemplateBlock.objects.filter(pk=pk).delete()
        return HttpResponse(status=204)


# ─── Concrete (Plan) Weeks ───────────────────────────────────────────────────

def _current_or_next_monday() -> date:
    today = date.today()
    return week_monday(today)


class PlanWeekListView(View):
    def get(self, request):
        weeks = PlanWeek.objects.select_related("source_template").order_by("-start_date")
        return render(request, "schedule/week_list.html", {"weeks": weeks})


class PlanWeekView(View):
    """View/edit a specific concrete week identified by its Monday date (YYYY-MM-DD)."""

    def get(self, request, start_date: str):
        from timetrack.core.models import Category

        start = date.fromisoformat(start_date)
        plan_week = PlanWeek.objects.filter(start_date=start).first()
        clone_form = CloneTemplateForm()
        prev_monday = start - timedelta(days=7)
        next_monday = start + timedelta(days=7)
        days = [start + timedelta(days=i) for i in range(7)]
        today = date.today()
        today_day_index = (today - start).days if 0 <= (today - start).days <= 6 else 0
        registry = get_registry()
        grid_data = json.dumps([]) if not plan_week else json.dumps(
            _blocks_to_grid(plan_week.blocks.select_related("category").all(), date_field=True)
        )
        stats = week_stats(plan_week) if plan_week else {}

        # Training plan banner + suggestions
        active_plan = None
        current_plan_week = None
        viewed_tplan_week = None
        plan_estimated_minutes = None
        plan_sessions = []
        strava_connected = False
        try:
            from django.db.models import Count as _Count
            from timetrack.plugins.running.models import RunSession as _RunSession, TrainingPlan
            from timetrack.plugins.running.services import (
                estimate_session_minutes,
                estimate_week_minutes,
                get_current_plan_week,
            )
            active_plan = TrainingPlan.objects.filter(is_active=True).first()
            if active_plan:
                current_plan_week = get_current_plan_week(active_plan)
                if current_plan_week:
                    plan_estimated_minutes = estimate_week_minutes(
                        current_plan_week, active_plan
                    )
                # Sessions for the VIEWED week (may differ from today's plan week)
                if active_plan.start_date <= start:
                    delta = (start - active_plan.start_date).days
                    viewed_tplan_week = active_plan.weeks.filter(
                        week_number=delta // 7 + 1
                    ).first()
                    if viewed_tplan_week:
                        run_type_counts = {}
                        if plan_week:
                            for row in (
                                _RunSession.objects
                                .filter(plan_block__week=plan_week)
                                .values("run_type")
                                .annotate(n=_Count("id"))
                            ):
                                run_type_counts[row["run_type"]] = row["n"]
                        for s in viewed_tplan_week.sessions.all():
                            est = max(estimate_session_minutes(s, active_plan), 30)
                            plan_sessions.append({
                                "pk": s.pk,
                                "run_type": s.run_type,
                                "title": f"{s.get_run_type_display()} – {float(s.target_km):.1f} km",
                                "estimated_minutes": est,
                                "target_km": float(s.target_km),
                                "day_of_week": s.day_of_week,
                                "notes": s.notes,
                                "scheduled_count": run_type_counts.get(s.run_type, 0),
                            })
        except Exception:
            pass
        try:
            from timetrack.strava.oauth import is_connected as strava_is_connected
            strava_connected = strava_is_connected()
        except Exception:
            pass

        # Annotate each active WeeklyTask with how many blocks are scheduled this week.
        from django.db.models import Count, Q
        weekly_tasks = (
            WeeklyTask.objects
            .filter(is_active=True)
            .select_related("category")
            .annotate(
                scheduled_count=Count(
                    "scheduled_blocks",
                    filter=Q(scheduled_blocks__week=plan_week) if plan_week else Q(pk__isnull=True),
                )
            )
        )

        # Collect plugin-provided suggestion chips (e.g. practice goals).
        plugin_suggestions = []
        for _plugin in registry.all():
            plugin_suggestions.extend(_plugin.get_suggestions(plan_week))

        # Category PKs for chip defaults
        from timetrack.core.models import Category as _Cat
        _exercise_cat = _Cat.objects.filter(name="Exercise").first()
        exercise_category_pk = _exercise_cat.pk if _exercise_cat else ""

        return render(
            request,
            "schedule/week_view.html",
            {
                "plan_week": plan_week,
                "start_date": start,
                "days": days,
                "prev_monday": prev_monday,
                "next_monday": next_monday,
                "clone_form": clone_form,
                "grid_data": grid_data,
                "plugins": registry.all(),
                "block_form": PlanBlockForm(),
                "categories": Category.objects.all(),
                "weekly_tasks": weekly_tasks,
                "plugin_suggestions": plugin_suggestions,
                "exercise_category_pk": exercise_category_pk,
                "plan_sessions": plan_sessions,
                "day_names": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
                "stats": stats,
                "time_zone": settings.TIME_ZONE,
                "active_plan": active_plan,
                "current_plan_week": current_plan_week,
                "viewed_tplan_week": viewed_tplan_week,
                "plan_estimated_minutes": plan_estimated_minutes,
                "strava_connected": strava_connected,
                "today_day_index": today_day_index,
            },
        )

    def post(self, request, start_date: str):
        """Clone a template into this week."""
        start = date.fromisoformat(start_date)
        form = CloneTemplateForm(request.POST)
        if form.is_valid():
            try:
                clone_template_to_week(
                    form.cleaned_data["template"],
                    start,
                    replace=form.cleaned_data["replace"],
                )
                messages.success(request, f"Cloned '{form.cleaned_data['template'].name}' into this week.")
            except ValueError as e:
                messages.error(request, str(e) + " Tick 'Replace existing blocks' to overwrite.")
        return redirect("week-view", start_date=start_date)


class PlanWeekCurrentView(View):
    def get(self, request):
        monday = _current_or_next_monday()
        return redirect("week-view", start_date=monday.isoformat())


# ─── Plan Blocks ─────────────────────────────────────────────────────────────

class PlanBlockCreateView(View):
    def post(self, request, week_pk):
        week = get_object_or_404(PlanWeek, pk=week_pk)
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
        form = PlanBlockForm(data)
        if form.is_valid():
            block = form.save(commit=False)
            block.week = week
            block.save()
            # Apply plugin default categories when none supplied
            if not block.category_id and block.plugin_slug:
                from timetrack.core.models import Category as _Cat
                _plugin_defaults = {"running": "Exercise", "practice": "Music"}
                _cat_name = _plugin_defaults.get(block.plugin_slug)
                if _cat_name:
                    _cat = _Cat.objects.filter(name=_cat_name).first()
                    if _cat:
                        block.category = _cat
                        block.save(update_fields=["category"])

            # Auto-create RunSession when dragged from a running plan session chip
            tps_id = data.get("training_plan_session_id")
            if tps_id:
                try:
                    from timetrack.plugins.running.models import RunSession, TrainingPlanSession
                    tps = TrainingPlanSession.objects.get(pk=int(tps_id))
                    RunSession.objects.create(
                        plan_block=block,
                        run_type=tps.run_type,
                        planned_km=tps.target_km,
                    )
                    if not block.plugin_slug:
                        block.plugin_slug = "running"
                        block.save(update_fields=["plugin_slug"])
                except Exception:
                    pass
            # Auto-create PracticeSession when dragged from a practice goal chip
            practice_goal_id = data.get("practice_goal_id")
            if practice_goal_id:
                try:
                    from timetrack.plugins.practice.models import PracticeGoal, PracticeSession
                    goal = PracticeGoal.objects.get(pk=int(practice_goal_id))
                    PracticeSession.objects.create(
                        plan_block=block,
                        goal=goal,
                        instrument=goal.instrument,
                        focus=goal.focus,
                        planned_minutes=goal.duration_minutes,
                    )
                    if not block.plugin_slug:
                        block.plugin_slug = "practice"
                        block.save(update_fields=["plugin_slug"])
                except Exception:
                    pass
            registry = get_registry()
            # For blocks created manually with a plugin (no chip drag), init
            # the plugin data row now so the edit panel always updates an
            # existing record rather than trying to insert a new one.
            if block.plugin_slug and not tps_id and not practice_goal_id:
                _plugin = registry.get(block.plugin_slug)
                if _plugin:
                    _plugin.init_block_data(block)
            plugin = registry.get(block.plugin_slug) if block.plugin_slug else None
            return render(
                request,
                "schedule/partials/block_chip.html",
                {"block": block, "plugin": plugin, "is_template": False},
            )
        return JsonResponse({"errors": form.errors}, status=400)


class PlanBlockUpdateView(View):
    def get(self, request, pk):
        from timetrack.core.models import Category

        block = get_object_or_404(PlanBlock, pk=pk)
        form = PlanBlockForm(instance=block)
        registry = get_registry()
        plugin = registry.get(block.plugin_slug) if block.plugin_slug else None
        plugin_form = plugin.get_plan_form(block) if plugin else None
        return render(
            request,
            "schedule/partials/block_edit_panel.html",
            {
                "block": block, "form": form, "plugin_form": plugin_form,
                "is_template": False, "categories": Category.objects.all(),
            },
        )

    def post(self, request, pk):
        block = get_object_or_404(PlanBlock, pk=pk)
        data = json.loads(request.body) if request.content_type == "application/json" else request.POST
        form = PlanBlockForm(data, instance=block)
        if form.is_valid():
            block = form.save()
            registry = get_registry()
            plugin = registry.get(block.plugin_slug) if block.plugin_slug else None
            if plugin:
                plugin_form = plugin.get_plan_form(block, data)
                if plugin_form and plugin_form.is_valid():
                    session = plugin_form.save(commit=False)
                    if session.pk is None:
                        session.plan_block = block
                    session.save()
            # mark week as draft again after edit
            block.week.status = "draft"
            block.week.save(update_fields=["status"])
            return render(
                request,
                "schedule/partials/block_chip.html",
                {"block": block, "plugin": plugin, "is_template": False},
            )
        return JsonResponse({"errors": form.errors}, status=400)

    def patch(self, request, pk):
        block = get_object_or_404(PlanBlock, pk=pk)
        body = json.loads(request.body)
        for field in ("start_time", "end_time", "date"):
            if field in body:
                setattr(block, field, body[field])
        block.week.status = "draft"
        block.week.save(update_fields=["status"])
        block.save()
        registry = get_registry()
        plugin = registry.get(block.plugin_slug) if block.plugin_slug else None
        return render(
            request,
            "schedule/partials/block_chip.html",
            {"block": block, "plugin": plugin, "is_template": False},
        )

    def delete(self, request, pk):
        block = get_object_or_404(PlanBlock, pk=pk)
        week = block.week
        week.status = "draft"
        if block.gcal_event_id:
            pending = week.gcal_pending_delete_ids or []
            if block.gcal_event_id not in pending:
                pending.append(block.gcal_event_id)
            week.gcal_pending_delete_ids = pending
        week.save(update_fields=["status", "gcal_pending_delete_ids"])
        block.delete()
        return HttpResponse(status=204)


# ─── Stats partial ───────────────────────────────────────────────────────────

class PlanWeekStatsView(View):
    def get(self, request, week_pk):
        week = get_object_or_404(PlanWeek, pk=week_pk)
        return render(
            request,
            "schedule/partials/week_stats.html",
            {"stats": week_stats(week)},
        )


# ─── Google Calendar push (delegated to gcal app) ────────────────────────────

class PushToGCalView(View):
    def post(self, request, week_pk):
        from timetrack.gcal.sync import push_week

        week = get_object_or_404(PlanWeek, pk=week_pk)
        try:
            result = push_week(week)
            msg = f"Pushed: {result['created']} created, {result['updated']} updated, {result['skipped']} skipped, {result['deleted']} deleted."
        except Exception as e:
            msg = f"Error: {e}"
        if request.headers.get("HX-Request"):
            return HttpResponse(f'<p class="text-sm text-green-700">{msg}</p>')
        return redirect("week-view", start_date=week.start_date.isoformat())


# ─── Copy week to next week ───────────────────────────────────────────────────

class CopyWeekForwardView(View):
    """Clone a concrete week's blocks forward by one week (not from a template)."""

    def post(self, request, week_pk):
        src_week = get_object_or_404(PlanWeek, pk=week_pk)
        new_start = src_week.start_date + timedelta(weeks=1)
        existing = PlanWeek.objects.filter(start_date=new_start).first()

        replace = request.POST.get("replace") == "1"
        if existing and not replace:
            messages.error(
                request,
                f"A plan for {new_start} already exists. Use 'Replace' to overwrite it.",
            )
            return redirect("week-view", start_date=src_week.start_date.isoformat())

        if existing and replace:
            existing.blocks.all().delete()
            dest_week = existing
            dest_week.source_template = src_week.source_template
            dest_week.status = "draft"
            dest_week.save()
        else:
            dest_week = PlanWeek.objects.create(
                start_date=new_start,
                source_template=src_week.source_template,
            )

        registry = get_registry()
        for src_block in src_week.blocks.select_related("category").all():
            new_date = src_block.date + timedelta(weeks=1)
            new_block = PlanBlock.objects.create(
                week=dest_week,
                date=new_date,
                start_time=src_block.start_time,
                end_time=src_block.end_time,
                title=src_block.title,
                category=src_block.category,
                notes=src_block.notes,
                plugin_slug=src_block.plugin_slug,
                source_template_block=src_block.source_template_block,
            )
            if src_block.plugin_slug:
                plugin = registry.get(src_block.plugin_slug)
                if plugin:
                    # Clone plugin data from the source plan block
                    plugin.clone_plan_block_data(src_block, new_block)

        messages.success(request, f"Copied to week of {new_start}.")
        return redirect("week-view", start_date=new_start.isoformat())


# ─── Helper ──────────────────────────────────────────────────────────────────

def _blocks_to_grid(blocks, date_field: bool) -> list:
    """Serialize blocks to JSON-friendly dicts for the frontend grid."""
    result = []
    for b in blocks:
        d = {
            "id": b.pk,
            "title": b.title,
            "start_time": b.start_time.strftime("%H:%M"),
            "end_time": b.end_time.strftime("%H:%M"),
            "category_color": b.category.color if b.category else "#6366f1",
            "category_name": b.category.name if b.category else "",
            "plugin_slug": b.plugin_slug,
            "notes": b.notes,
        }
        if date_field:
            d["date"] = b.date.isoformat()
            d["day_of_week"] = b.date.weekday()
        else:
            d["day_of_week"] = b.day_of_week
        result.append(d)
    return result


# ─── Weekly Tasks ────────────────────────────────────────────────────────────

class WeeklyTaskListView(View):
    def get(self, request):
        tasks = WeeklyTask.objects.select_related("category").all()
        form = WeeklyTaskForm()
        from timetrack.core.models import Category
        return render(request, "schedule/weekly_tasks.html", {
            "tasks": tasks, "form": form, "categories": Category.objects.all(),
        })

    def post(self, request):
        form = WeeklyTaskForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect("weekly-tasks")
        tasks = WeeklyTask.objects.select_related("category").all()
        from timetrack.core.models import Category
        return render(request, "schedule/weekly_tasks.html", {
            "tasks": tasks, "form": form, "categories": Category.objects.all(),
        })


class WeeklyTaskDeleteView(View):
    def post(self, request, pk):
        get_object_or_404(WeeklyTask, pk=pk).delete()
        return redirect("weekly-tasks")


class WeeklyTaskToggleView(View):
    def post(self, request, pk):
        task = get_object_or_404(WeeklyTask, pk=pk)
        task.is_active = not task.is_active
        task.save(update_fields=["is_active"])
        return redirect("weekly-tasks")


class PlanWeekHistoryView(View):
    """Cross-week history table — last 26 plan weeks with aggregated stats."""

    def get(self, request):
        recent = PlanWeek.objects.order_by("-start_date")[:26]
        rows = []
        max_km = 1  # avoid division by zero
        for w in recent:
            s = week_stats(w)
            km = float(s["run"]["total_planned_km"] or 0)
            if km > max_km:
                max_km = km
            rows.append({"week": w, "stats": s, "km": km})
        for row in rows:
            row["km_pct"] = int(row["km"] / max_km * 100)
        return render(request, "schedule/history.html", {"rows": rows})
