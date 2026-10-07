from django import forms

from .models import (
    DailyCheckIn,
    PlanBlock,
    PlanWeekReflection,
    TemplateBlock,
    TemplateWeek,
    WeeklyGoal,
    WeeklyTask,
)


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


class BrainDumpForm(forms.Form):
    thoughts = forms.CharField(widget=forms.Textarea(attrs={
        "rows": 3, "class": "form-input w-full text-sm",
        "placeholder": "Everything on your mind — one item per line…",
    }))


class BrainDumpScheduleForm(forms.ModelForm):
    class Meta:
        model = PlanBlock
        fields = ["date", "start_time", "end_time", "category"]
        widgets = {
            "date": forms.HiddenInput(),
            "start_time": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "end_time": forms.TimeInput(attrs={"type": "time", "class": "form-input"}),
            "category": forms.Select(attrs={"class": "form-select"}),
        }

    def clean(self):
        data = super().clean()
        start, end = data.get("start_time"), data.get("end_time")
        if start and end and end <= start:
            self.add_error("end_time", "End time must be after start time.")
        return data


class CloneTemplateForm(forms.Form):
    template = forms.ModelChoiceField(queryset=TemplateWeek.objects.all())
    replace = forms.BooleanField(required=False, label="Replace existing blocks if week exists")


class PlanningReflectionForm(forms.ModelForm):
    class Meta:
        model = PlanWeekReflection
        fields = ["weekly_intention"]
        widgets = {
            "weekly_intention": forms.Textarea(attrs={"rows": 3}),
        }


class WeeklyGoalForm(forms.ModelForm):
    class Meta:
        model = WeeklyGoal
        fields = ["title", "category", "priority", "notes"]
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


class ReviewReflectionForm(forms.ModelForm):
    class Meta:
        model = PlanWeekReflection
        fields = ["wins", "misses", "lessons", "next_week_notes", "energy_score"]
        widgets = {
            "wins": forms.Textarea(attrs={"rows": 3}),
            "misses": forms.Textarea(attrs={"rows": 3}),
            "lessons": forms.Textarea(attrs={"rows": 3}),
            "next_week_notes": forms.Textarea(attrs={"rows": 3}),
            "energy_score": forms.NumberInput(attrs={"min": 1, "max": 5}),
        }


class DailyCheckInForm(forms.ModelForm):
    class Meta:
        model = DailyCheckIn
        fields = ["intention", "general_aims", "energy_score"]
        widgets = {
            "intention": forms.Textarea(attrs={"rows": 2}),
            "general_aims": forms.Textarea(attrs={"rows": 3}),
            "energy_score": forms.NumberInput(attrs={"min": 1, "max": 5}),
        }


class DailyRecapForm(forms.ModelForm):
    class Meta:
        model = DailyCheckIn
        fields = ["recap_wins", "recap_misses", "recap_energy_score", "notes_for_tomorrow"]
        widgets = {
            "recap_wins": forms.Textarea(attrs={"rows": 3}),
            "recap_misses": forms.Textarea(attrs={"rows": 3}),
            "notes_for_tomorrow": forms.Textarea(attrs={"rows": 3}),
            "recap_energy_score": forms.NumberInput(attrs={"min": 1, "max": 5}),
        }
