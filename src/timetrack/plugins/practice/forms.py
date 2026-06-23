from django import forms

from .models import PracticeSession


class PracticeSessionForm(forms.ModelForm):
    class Meta:
        model = PracticeSession
        fields = ["instrument", "focus", "pieces", "planned_minutes", "actual_minutes", "notes"]
        widgets = {
            "pieces": forms.Textarea(attrs={"rows": 2}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
