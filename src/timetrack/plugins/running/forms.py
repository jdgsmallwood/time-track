from django import forms

from .models import RunSession


class RunSessionForm(forms.ModelForm):
    class Meta:
        model = RunSession
        fields = ["run_type", "planned_km", "actual_km", "planned_pace", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}
