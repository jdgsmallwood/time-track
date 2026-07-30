from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views import View

from timetrack.schedule.models import PlanBlock

from .forms import MeetingNotesForm
from .models import MeetingNotes


class MeetingNotesView(View):
    """Modal for taking minutes on a single plan block."""

    def get(self, request, block_pk):
        block = get_object_or_404(PlanBlock, pk=block_pk)
        notes, _created = MeetingNotes.objects.get_or_create(plan_block=block)
        form = MeetingNotesForm(instance=notes, prefix="meeting")
        return render(request, "meeting/minutes_modal.html", {"block": block, "form": form})

    def post(self, request, block_pk):
        block = get_object_or_404(PlanBlock, pk=block_pk)
        notes, _created = MeetingNotes.objects.get_or_create(plan_block=block)
        form = MeetingNotesForm(request.POST, instance=notes, prefix="meeting")
        if form.is_valid():
            form.save()
            response = HttpResponse(status=204)
            response["HX-Refresh"] = "true"
            return response
        return render(
            request,
            "meeting/minutes_modal.html",
            {"block": block, "form": form},
            status=400,
        )
