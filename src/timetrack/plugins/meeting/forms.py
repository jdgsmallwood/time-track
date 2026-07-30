from django import forms

from .models import MeetingNotes


class MeetingNotesForm(forms.ModelForm):
    class Meta:
        model = MeetingNotes
        fields = ["minutes"]
        widgets = {
            "minutes": forms.Textarea(attrs={"rows": 16}),
        }
