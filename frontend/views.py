from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from frontend.models import UserProfile, Ingredient
from frontend.forms import CustomRegistrationForm, CustomLoginForm, IngredientForm
import traceback

User = get_user_model()

def home_page(request):
    return render(request, 'home.html')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home_page')
    
    if request.method == 'POST':
        form = CustomRegistrationForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, 'Rejestracja przebiegła pomyślnie! Możesz się teraz zalogować.')
                return redirect('login_view')
            except Exception as e:
                traceback.print_exc()
                messages.error(request, f'Wystąpił błąd podczas rejestracji: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CustomRegistrationForm()
    
    return render(request, 'auth/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home_page')
    
    if request.method == 'POST':
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Ustaw długość sesji w zależności od "Zapamiętaj mnie"
                if not remember_me:
                    request.session.set_expiry(0)
                else:
                    request.session.set_expiry(1209600)  # 2 tygodnie
                
                messages.success(request, f'Witaj ponownie, {user.first_name or user.username}!')
                
                # Przekieruj w zależności od roli
                try:
                    if user.userprofile.role == 'manager':
                        return redirect('manage_dashboard')
                    else:
                        return redirect('home_page')
                except UserProfile.DoesNotExist:
                    UserProfile.objects.create(user=user, role='client')
                    return redirect('home_page')
            else:
                messages.error(request, 'Nieprawidłowe dane logowania.')
    else:
        form = CustomLoginForm()
    
    return render(request, 'auth/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Zostałeś pomyślnie wylogowany. Do zobaczenia!')
    return redirect('home_page')

def user_is_manager(user):
    """Sprawdza czy użytkownik jest menadżerem"""
    try:
        return user.is_authenticated and user.userprofile.role == 'manager'
    except UserProfile.DoesNotExist:
        return False

@login_required
def manage_dashboard(request):
    """Dashboard zarządzania dla menadżerów"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Podstawowe statystyki
    context = {
        'total_ingredients': Ingredient.objects.filter(is_deleted=False).count(),
        'total_dishes': 0,  # Dodamy później
        'total_plans': 0,   # Dodamy później
        'active_subscriptions': 0,  # Dodamy później
    }
    
    return render(request, 'management/dashboard.html', context)

@login_required
def ingredient_list(request):
    """Lista składników z paginacją i wyszukiwaniem"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Parametry z GET
    search = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '25')
    show_deleted = request.GET.get('show_deleted', False)
    
    # Walidacja per_page
    if per_page not in ['10', '25', '50']:
        per_page = '25'
    
    # Bazowe query
    ingredients = Ingredient.objects.all()
    
    # Filtrowanie usuniętych
    if not show_deleted:
        ingredients = ingredients.filter(is_deleted=False)
    
    # Wyszukiwanie
    if search:
        ingredients = ingredients.filter(
            Q(name__icontains=search)
        )
    
    # Sortowanie
    ingredients = ingredients.order_by('name')
    
    # Paginacja
    paginator = Paginator(ingredients, int(per_page))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'per_page': per_page,
        'show_deleted': show_deleted,
        'total_count': ingredients.count(),
    }
    
    return render(request, 'management/ingredients/list.html', context)

@login_required
def ingredient_add(request):
    """Dodawanie nowego składnika"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    if request.method == 'POST':
        form = IngredientForm(request.POST)
        if form.is_valid():
            ingredient = form.save()
            messages.success(request, f'Składnik "{ingredient.name}" został dodany pomyślnie.')
            return redirect('ingredient_list')
    else:
        form = IngredientForm()
    
    return render(request, 'management/ingredients/form.html', {
        'form': form,
        'title': 'Dodaj składnik',
        'submit_text': 'Dodaj składnik'
    })

@login_required
def ingredient_edit(request, pk):
    """Edycja składnika"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    try:
        ingredient = Ingredient.objects.get(pk=pk)
    except Ingredient.DoesNotExist:
        messages.error(request, 'Składnik nie został znaleziony.')
        return redirect('ingredient_list')
    
    if request.method == 'POST':
        form = IngredientForm(request.POST, instance=ingredient)
        if form.is_valid():
            ingredient = form.save()
            messages.success(request, f'Składnik "{ingredient.name}" został zaktualizowany.')
            return redirect('ingredient_list')
    else:
        form = IngredientForm(instance=ingredient)
    
    return render(request, 'management/ingredients/form.html', {
        'form': form,
        'ingredient': ingredient,
        'title': f'Edytuj składnik: {ingredient.name}',
        'submit_text': 'Zaktualizuj składnik'
    })

@login_required
def ingredient_delete(request, pk):
    """Soft delete składnika"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    try:
        ingredient = Ingredient.objects.get(pk=pk)
    except Ingredient.DoesNotExist:
        messages.error(request, 'Składnik nie został znaleziony.')
        return redirect('ingredient_list')
    
    if request.method == 'POST':
        if ingredient.is_deleted:
            # Przywróć składnik
            ingredient.is_deleted = False
            ingredient.save()
            messages.success(request, f'Składnik "{ingredient.name}" został przywrócony.')
        else:
            # Usuń składnik (soft delete)
            ingredient.delete()  # Korzysta z custom delete() method z modelu
            messages.success(request, f'Składnik "{ingredient.name}" został usunięty.')
        
        return redirect('ingredient_list')
    
    return render(request, 'management/ingredients/confirm_delete.html', {
        'ingredient': ingredient
    })