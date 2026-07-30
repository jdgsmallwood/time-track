from django.urls import path

from .views import MeetingNotesView

urlpatterns = [
    path("blocks/<int:block_pk>/minutes/", MeetingNotesView.as_view(), name="meeting-notes"),
]
