from django import forms

from .models import PlanBlock, TemplateBlock, TemplateWeek, WeeklyTask


class TemplateWeekForm(forms.ModelForm):
    class Meta:
        model = TemplateWeek
        fields = ["name", "description", "is_default"]


class TemplateBlockForm(forms.ModelForm):
    class Meta:
        model = TemplateBlock
        fields = ["day_of_week", "start_time", "end_time", "title", "category", "notes", "plugin_slug"]
        widgets = {
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "plugin_slug": forms.HiddenInput(),
        }


class PlanBlockForm(forms.ModelForm):
    class Meta:
        model = PlanBlock
        fields = ["date", "start_time", "end_time", "title", "category", "weekly_task", "notes", "plugin_slug"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "start_time": forms.TimeInput(attrs={"type": "time"}),
            "end_time": forms.TimeInput(attrs={"type": "time"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
            "plugin_slug": forms.HiddenInput(),
            "weekly_task": forms.HiddenInput(),
        }


class WeeklyTaskForm(forms.ModelForm):
    class Meta:
        model = WeeklyTask
        fields = ["title", "duration_minutes", "category", "recurrence_count", "notes"]
        widgets = {
            "notes": forms.TextInput(),
        }


class CloneTemplateForm(forms.Form):
    template = forms.ModelChoiceField(queryset=TemplateWeek.objects.all())
    replace = forms.BooleanField(required=False, label="Replace existing blocks if week exists")
