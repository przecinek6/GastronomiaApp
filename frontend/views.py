from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from frontend.models import UserProfile, Ingredient, Dish, DishIngredient
from frontend.forms import CustomRegistrationForm, CustomLoginForm, IngredientForm, DishForm, DishIngredientFormSet
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
        'total_dishes': Dish.objects.filter(is_deleted=False).count(),
        'total_plans': 0,   # Dodamy później
        'active_subscriptions': 0,  # Dodamy później
    }
    
    return render(request, 'management/dashboard.html', context)

# ==========================================
# ZARZĄDZANIE SKŁADNIKAMI
# ==========================================

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
    
    ingredient = get_object_or_404(Ingredient, pk=pk)
    
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
    
    ingredient = get_object_or_404(Ingredient, pk=pk)
    
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

# ==========================================
# ZARZĄDZANIE DANIAMI
# ==========================================

@login_required
def dish_list(request):
    """Lista dań z paginacją i wyszukiwaniem"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Parametry z GET
    search = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '25')
    show_deleted = request.GET.get('show_deleted', False)
    meal_type = request.GET.get('meal_type', '')
    
    # Walidacja per_page
    if per_page not in ['10', '25', '50']:
        per_page = '25'
    
    # Bazowe query z prefetch dla optymalizacji
    dishes = Dish.objects.prefetch_related('dishingredient_set__ingredient').all()
    
    # Filtrowanie usuniętych
    if not show_deleted:
        dishes = dishes.filter(is_deleted=False)
    
    # Wyszukiwanie
    if search:
        dishes = dishes.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    # Filtrowanie po typie posiłku
    if meal_type:
        dishes = dishes.filter(meal_type=meal_type)
    
    # Sortowanie
    dishes = dishes.order_by('name')
    
    # Paginacja
    paginator = Paginator(dishes, int(per_page))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'per_page': per_page,
        'show_deleted': show_deleted,
        'meal_type': meal_type,
        'meal_type_choices': Dish.MEAL_TYPE_CHOICES,
        'total_count': dishes.count(),
    }
    
    return render(request, 'management/dishes/list.html', context)

@login_required
def dish_add(request):
    """Dodawanie nowego dania"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES)
        ingredient_formset = DishIngredientFormSet(request.POST, prefix='ingredients')
        
        if form.is_valid() and ingredient_formset.is_valid():
            try:
                with transaction.atomic():
                    # Zapisz danie
                    dish = form.save()
                    
                    # Zapisz składniki
                    for ingredient_form in ingredient_formset:
                        if ingredient_form.cleaned_data and not ingredient_form.cleaned_data.get('DELETE', False):
                            ingredient = ingredient_form.cleaned_data['ingredient']
                            quantity = ingredient_form.cleaned_data['quantity_grams']
                            
                            DishIngredient.objects.create(
                                dish=dish,
                                ingredient=ingredient,
                                quantity_grams=quantity
                            )
                    
                    messages.success(request, f'Danie "{dish.name}" zostało dodane pomyślnie.')
                    return redirect('dish_list')
            except Exception as e:
                messages.error(request, f'Wystąpił błąd podczas zapisywania: {str(e)}')
    else:
        form = DishForm()
        ingredient_formset = DishIngredientFormSet(prefix='ingredients')
    
    return render(request, 'management/dishes/form.html', {
        'form': form,
        'ingredient_formset': ingredient_formset,
        'title': 'Dodaj danie',
        'submit_text': 'Dodaj danie'
    })

@login_required
def dish_edit(request, pk):
    """Edycja dania"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    dish = get_object_or_404(Dish, pk=pk)
    
    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES, instance=dish)
        ingredient_formset = DishIngredientFormSet(request.POST, prefix='ingredients')
        
        if form.is_valid() and ingredient_formset.is_valid():
            try:
                with transaction.atomic():
                    # Zapisz danie
                    dish = form.save()
                    
                    # Usuń stare składniki
                    DishIngredient.objects.filter(dish=dish).delete()
                    
                    # Zapisz nowe składniki
                    for ingredient_form in ingredient_formset:
                        if ingredient_form.cleaned_data and not ingredient_form.cleaned_data.get('DELETE', False):
                            ingredient = ingredient_form.cleaned_data['ingredient']
                            quantity = ingredient_form.cleaned_data['quantity_grams']
                            
                            DishIngredient.objects.create(
                                dish=dish,
                                ingredient=ingredient,
                                quantity_grams=quantity
                            )
                    
                    messages.success(request, f'Danie "{dish.name}" zostało zaktualizowane.')
                    return redirect('dish_list')
            except Exception as e:
                messages.error(request, f'Wystąpił błąd podczas zapisywania: {str(e)}')
    else:
        form = DishForm(instance=dish)
        
        # Przygotuj dane dla formset na podstawie istniejących składników
        initial_data = []
        for dish_ingredient in dish.dishingredient_set.all():
            initial_data.append({
                'ingredient': dish_ingredient.ingredient.id,
                'quantity_grams': dish_ingredient.quantity_grams
            })
        
        ingredient_formset = DishIngredientFormSet(
            initial=initial_data,
            prefix='ingredients'
        )
    
    return render(request, 'management/dishes/form.html', {
        'form': form,
        'ingredient_formset': ingredient_formset,
        'dish': dish,
        'title': f'Edytuj danie: {dish.name}',
        'submit_text': 'Zaktualizuj danie'
    })

@login_required
def dish_delete(request, pk):
    """Soft delete dania"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    dish = get_object_or_404(Dish, pk=pk)
    
    if request.method == 'POST':
        if dish.is_deleted:
            # Przywróć danie
            dish.is_deleted = False
            dish.save()
            messages.success(request, f'Danie "{dish.name}" zostało przywrócone.')
        else:
            # Usuń danie (soft delete)
            dish.delete()  # Korzysta z custom delete() method z modelu
            messages.success(request, f'Danie "{dish.name}" zostało usunięte.')
        
        return redirect('dish_list')
    
    return render(request, 'management/dishes/confirm_delete.html', {
        'dish': dish
    })

# ==========================================
# API ENDPOINTY
# ==========================================

@login_required
@require_GET
def ingredient_data_api(request, ingredient_id):
    """API endpoint do pobierania danych składnika"""
    if not user_is_manager(request.user):
        return JsonResponse({'error': 'Brak uprawnień'}, status=403)
    
    try:
        ingredient = Ingredient.objects.get(id=ingredient_id, is_deleted=False)
        data = {
            'name': ingredient.name,
            'calories_per_100g': float(ingredient.calories_per_100g),
            'protein_per_100g': float(ingredient.protein_per_100g),
            'fat_per_100g': float(ingredient.fat_per_100g),
            'price_per_100g': float(ingredient.price_per_100g)
        }
        return JsonResponse(data)
    except Ingredient.DoesNotExist:
        return JsonResponse({'error': 'Składnik nie znaleziony'}, status=404)

@login_required
@require_GET
def ingredients_list_api(request):
    """API endpoint do pobierania listy składników"""
    if not user_is_manager(request.user):
        return JsonResponse({'error': 'Brak uprawnień'}, status=403)
    
    ingredients = Ingredient.objects.filter(is_deleted=False).values(
        'id', 'name', 'calories_per_100g', 'protein_per_100g', 'fat_per_100g', 'price_per_100g'
    )
    
    # Konwertuj Decimal na float dla JSON
    data = []
    for ingredient in ingredients:
        data.append({
            'id': ingredient['id'],
            'name': ingredient['name'],
            'calories_per_100g': float(ingredient['calories_per_100g']),
            'protein_per_100g': float(ingredient['protein_per_100g']),
            'fat_per_100g': float(ingredient['fat_per_100g']),
            'price_per_100g': float(ingredient['price_per_100g'])
        })
    
    return JsonResponse({'ingredients': data})