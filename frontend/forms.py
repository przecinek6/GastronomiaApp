from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from datetime import date

User = get_user_model()

class CustomRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Twój adres email'
        })
    )
    
    first_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Imię'
        })
    )
    
    last_name = forms.CharField(
        max_length=30,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Nazwisko'
        })
    )
    
    phone = forms.CharField(
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Numer telefonu (opcjonalnie)'
        })
    )
    
    address = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors resize-none',
            'placeholder': 'Adres dostawy (opcjonalnie)',
            'rows': 3
        })
    )
    
    date_of_birth = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'type': 'date'
        })
    )
    
    terms_accepted = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500'
        })
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Dodaj klasy CSS do pól z UserCreationForm
        self.fields['username'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Nazwa użytkownika'
        })
        
        self.fields['password1'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Hasło'
        })
        
        self.fields['password2'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Potwierdź hasło'
        })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError('Użytkownik z tym adresem email już istnieje.')
        return email

    def clean_date_of_birth(self):
        date_of_birth = self.cleaned_data.get('date_of_birth')
        if date_of_birth and date_of_birth > date.today():
            raise ValidationError('Data urodzenia nie może być z przyszłości.')
        return date_of_birth

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
        return user


class CustomLoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Nazwa użytkownika lub email'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Hasło'
        })
    )
    
    remember_me = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500'
        })
    )