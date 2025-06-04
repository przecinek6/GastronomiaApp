from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from datetime import date
from frontend.models import Ingredient, Dish, DietPlan

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


class IngredientForm(forms.ModelForm):
    class Meta:
        model = Ingredient
        fields = ['name', 'calories_per_100g', 'protein_per_100g', 'fat_per_100g', 'price_per_100g']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Stylowanie pól formularza
        self.fields['name'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Nazwa składnika (np. Kurczak pierś)'
        })
        
        self.fields['calories_per_100g'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Kalorie na 100g (np. 165)',
            'step': '0.01',
            'min': '0'
        })
        
        self.fields['protein_per_100g'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Białko na 100g (np. 31.0)',
            'step': '0.01',
            'min': '0'
        })
        
        self.fields['fat_per_100g'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Tłuszcze na 100g (np. 3.6)',
            'step': '0.01',
            'min': '0'
        })
        
        self.fields['price_per_100g'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Cena za 100g (np. 12.50)',
            'step': '0.01',
            'min': '0'
        })
        
        # Polskie etykiety
        self.fields['name'].label = 'Nazwa składnika'
        self.fields['calories_per_100g'].label = 'Kalorie na 100g'
        self.fields['protein_per_100g'].label = 'Białko na 100g (g)'
        self.fields['fat_per_100g'].label = 'Tłuszcze na 100g (g)'
        self.fields['price_per_100g'].label = 'Cena za 100g (zł)'


class DishForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = ['name', 'meal_type', 'allergens', 'description', 'image']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Stylowanie pól formularza
        self.fields['name'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Nazwa dania (np. Pierś kurczaka z ryżem)'
        })
        
        self.fields['meal_type'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors'
        })
        
        self.fields['allergens'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors resize-none',
            'placeholder': 'Lista alergenów oddzielona przecinkami (np. gluten, laktoza)',
            'rows': 3
        })
        
        self.fields['description'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors resize-none',
            'placeholder': 'Opis dania...',
            'rows': 4
        })
        
        self.fields['image'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'accept': 'image/*'
        })
        
        # Polskie etykiety
        self.fields['name'].label = 'Nazwa dania'
        self.fields['meal_type'].label = 'Typ posiłku'
        self.fields['allergens'].label = 'Alergeny'
        self.fields['description'].label = 'Opis'
        self.fields['image'].label = 'Zdjęcie dania'
        
        # Opcjonalne pola
        self.fields['allergens'].required = False
        self.fields['description'].required = False
        self.fields['image'].required = False


class DishIngredientForm(forms.Form):
    ingredient = forms.ModelChoiceField(
        queryset=Ingredient.objects.filter(is_deleted=False),
        empty_label="Wybierz składnik...",
        widget=forms.Select(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors ingredient-select'
        })
    )
    
    quantity_grams = forms.DecimalField(
        max_digits=8,
        decimal_places=2,
        min_value=0.01,
        widget=forms.NumberInput(attrs={
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors quantity-input',
            'placeholder': 'Ilość w gramach',
            'step': '0.01',
            'min': '0.01'
        })
    )
    
    DELETE = forms.BooleanField(
        required=False,
        widget=forms.HiddenInput()
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['ingredient'].label = 'Składnik'
        self.fields['quantity_grams'].label = 'Ilość (g)'


class DishIngredientFormSet(forms.BaseFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def clean(self):
        """Sprawdza czy zostały dodane jakieś składniki"""
        if any(self.errors):
            return
            
        active_forms = 0
        for form in self.forms:
            if form.cleaned_data and not form.cleaned_data.get('DELETE', False):
                active_forms += 1
                
        if active_forms == 0:
            raise ValidationError('Danie musi zawierać przynajmniej jeden składnik.')


# Tworzenie formset dla składników w daniu
DishIngredientFormSet = forms.formset_factory(
    DishIngredientForm,
    formset=DishIngredientFormSet,
    extra=1,
    can_delete=True
)

class DietPlanForm(forms.ModelForm):
    class Meta:
        model = DietPlan
        fields = ['name', 'description', 'weekly_price', 'is_active']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Stylowanie pól formularza
        self.fields['name'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Nazwa planu (np. Plan Keto, Plan Standard)'
        })
        
        self.fields['description'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors resize-none',
            'placeholder': 'Opis planu dietetycznego, dla kogo jest przeznaczony, jakie ma korzyści...',
            'rows': 5
        })
        
        self.fields['weekly_price'].widget.attrs.update({
            'class': 'w-full px-4 py-3 rounded-lg border border-gray-300 focus:border-green-500 focus:outline-none transition-colors',
            'placeholder': 'Cena za tydzień (np. 149.99)',
            'step': '0.01',
            'min': '0'
        })
        
        self.fields['is_active'].widget.attrs.update({
            'class': 'w-4 h-4 text-green-600 border-gray-300 rounded focus:ring-green-500'
        })
        
        # Polskie etykiety
        self.fields['name'].label = 'Nazwa planu'
        self.fields['description'].label = 'Opis planu'
        self.fields['weekly_price'].label = 'Cena tygodniowa (zł)'
        self.fields['is_active'].label = 'Plan aktywny'
        
        # Help texts
        self.fields['weekly_price'].help_text = 'System automatycznie obliczy ceny miesięczne i roczne'
        self.fields['is_active'].help_text = 'Nieaktywne plany nie są widoczne dla klientów'
    
    def clean_weekly_price(self):
        weekly_price = self.cleaned_data.get('weekly_price')
        if weekly_price and weekly_price <= 0:
            raise ValidationError('Cena musi być większa od 0.')
        return weekly_price