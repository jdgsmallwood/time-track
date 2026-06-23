from django import forms

from .models import Category


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "color", "icon", "order"]
        widgets = {
            "color": forms.TextInput(attrs={"type": "color"}),
        }
