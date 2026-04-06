from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from clinic.booking_utils import is_shop_closed, slot_available
from clinic.models import Appointment, Pet, Service, ShopClosedDate

User = get_user_model()


class PetForm(forms.ModelForm):
    class Meta:
        model = Pet
        fields = [
            "name",
            "species",
            "breed",
            "birth_date",
            "medical_history",
            "vaccination_next_due",
        ]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}),
            "species": forms.Select(attrs={"class": "input"}),
            "breed": forms.TextInput(attrs={"class": "input"}),
            "birth_date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "vaccination_next_due": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "medical_history": forms.Textarea(attrs={"rows": 4, "class": "input"}),
        }


class AppointmentForm(forms.ModelForm):
    # Client chooses pet species in the booking form.
    pet_species = forms.ChoiceField(
        choices=Pet.PET_SPECIES_CHOICES,
        required=True,
        widget=forms.Select(attrs={"class": "input"}),
        label="Pet",
        help_text="Choose the animal type you are booking for.",
    )
    pet_name = forms.CharField(
        max_length=120,
        required=True,
        widget=forms.TextInput(attrs={"class": "input"}),
        label="Pet name",
    )
    pet_breed = forms.CharField(
        max_length=120,
        required=False,
        widget=forms.TextInput(attrs={"class": "input"}),
        label="Breed (optional)",
    )
    medical_history = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "input"}),
        label="Medical history (optional)",
    )
    vaccination_next_due = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "input"}),
        label="Vaccination next due (optional)",
    )

    class Meta:
        model = Appointment
        # NOTE: `pet` is NOT shown as a dropdown. We create/reuse a Pet record from the inputs above.
        fields = [
            "service",
            "appointment_date",
            "appointment_time",
            "is_emergency",
            "notes",
        ]
        widgets = {
            "service": forms.Select(attrs={"class": "input"}),
            "appointment_date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "appointment_time": forms.TimeInput(
                attrs={"type": "time", "step": "1800", "class": "input"}
            ),
            "notes": forms.Textarea(attrs={"rows": 3, "class": "input"}),
            "is_emergency": forms.CheckboxInput(attrs={"class": "checkbox"}),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["service"].queryset = Service.objects.all()

    def clean(self):
        data = super().clean()
        d = data.get("appointment_date")
        t = data.get("appointment_time")

        if d and is_shop_closed(d):
            raise ValidationError(
                "The clinic is closed on this date. Choose another day or contact us."
            )
        if d and t:
            self._over_capacity = not slot_available(d, t)
        else:
            self._over_capacity = False

        return data

    def save(self, commit=True):
        if not self.user:
            raise ValueError("AppointmentForm requires `user`.")

        inst = super().save(commit=False)
        inst.is_over_capacity = getattr(self, "_over_capacity", False)

        pet_species = self.cleaned_data["pet_species"]
        pet_name = self.cleaned_data["pet_name"]

        # Reuse existing pet if it matches owner+name+species.
        pet = Pet.objects.filter(
            owner=self.user, name=pet_name, species=pet_species
        ).first()
        if not pet:
            pet = Pet.objects.create(
                owner=self.user,
                name=pet_name,
                species=pet_species,
            )

        # Update optional pet details if provided.
        pet.breed = self.cleaned_data.get("pet_breed", "") or pet.breed
        pet.medical_history = self.cleaned_data.get("medical_history", "") or pet.medical_history
        pet.vaccination_next_due = self.cleaned_data.get("vaccination_next_due", None) or pet.vaccination_next_due
        pet.save()

        inst.pet = pet

        if commit:
            inst.save()
        return inst


class ShopClosedDateForm(forms.ModelForm):
    class Meta:
        model = ShopClosedDate
        fields = ["date", "reason"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "input"}),
            "reason": forms.TextInput(attrs={"class": "input", "placeholder": "e.g. Holiday"}),
        }

    def clean_date(self):
        d = self.cleaned_data["date"]
        qs = ShopClosedDate.objects.filter(date=d)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError("That date is already marked as closed.")
        return d
