from django import forms
from org.models import (
    Company,
    Plant,
    Department,
    Shop,
    Line,
    Station,
    Product,
)

INPUT_STYLE = "w-full rounded-lg border-gray-300 bg-white border p-2.5 text-sm focus:ring-2 focus:ring-sky-500 focus:border-sky-500"
CHECKBOX_STYLE = "h-4 w-4 text-sky-600 focus:ring-sky-500 border-gray-300 rounded"


class CompanyForm(forms.ModelForm):
    class Meta:
        model = Company
        fields = ["code", "name", "is_active"]
        widgets = {
            "code": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. DIXON"}),
            "name": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. Dixon Technologies Ltd"}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_STYLE}),
        }


class PlantForm(forms.ModelForm):
    TIMEZONE_CHOICES = [
        ("Asia/Kolkata", "Asia/Kolkata (IST)"),
        ("UTC", "UTC"),
        ("America/New_York", "America/New_York (EST)"),
        ("Asia/Shanghai", "Asia/Shanghai (CST)"),
    ]

    timezone = forms.ChoiceField(
        choices=TIMEZONE_CHOICES,
        widget=forms.Select(attrs={"class": INPUT_STYLE}),
        initial="Asia/Kolkata",
    )

    class Meta:
        model = Plant
        fields = ["company", "code", "name", "timezone", "is_active"]
        widgets = {
            "company": forms.Select(attrs={"class": INPUT_STYLE}),
            "code": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. P1"}),
            "name": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. Plant 1 Noida"}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_STYLE}),
        }


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["plant", "code", "name", "description", "is_active"]
        widgets = {
            "plant": forms.Select(attrs={"class": INPUT_STYLE}),
            "code": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. QA"}),
            "name": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. Quality Assurance"}),
            "description": forms.Textarea(attrs={"class": INPUT_STYLE, "rows": 3, "placeholder": "Department overview..."}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_STYLE}),
        }


class ShopForm(forms.ModelForm):
    class Meta:
        model = Shop
        fields = ["plant", "code", "name", "is_active"]
        widgets = {
            "plant": forms.Select(attrs={"class": INPUT_STYLE}),
            "code": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. SMT"}),
            "name": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. SMT Shop Floor"}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_STYLE}),
        }


class LineForm(forms.ModelForm):
    class Meta:
        model = Line
        fields = ["shop", "code", "name", "is_active"]
        widgets = {
            "shop": forms.Select(attrs={"class": INPUT_STYLE}),
            "code": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. L1"}),
            "name": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. Main SMT Line 1"}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_STYLE}),
        }


class StationForm(forms.ModelForm):
    class Meta:
        model = Station
        fields = ["line", "code", "name", "is_active"]
        widgets = {
            "line": forms.Select(attrs={"class": INPUT_STYLE}),
            "code": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. ST01"}),
            "name": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. Solder Paste Inspection"}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_STYLE}),
        }


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = ["company", "plant", "code", "name", "category", "position", "brand", "is_active"]
        widgets = {
            "company": forms.Select(attrs={"class": INPUT_STYLE}),
            "plant": forms.Select(attrs={"class": INPUT_STYLE}),
            "code": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. PRD-001"}),
            "name": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. Smart LED Board v2"}),
            "category": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. PCB Assembly"}),
            "position": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. Main Board"}),
            "brand": forms.TextInput(attrs={"class": INPUT_STYLE, "placeholder": "e.g. Dixon"}),
            "is_active": forms.CheckboxInput(attrs={"class": CHECKBOX_STYLE}),
        }
