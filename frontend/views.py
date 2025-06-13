from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model, update_session_auth_hash
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from frontend.models import UserProfile, Ingredient, Dish, DishIngredient, DietPlan, MealPlan, Subscription, DietChange, Payment, Delivery, ReferralProgram
from frontend.forms import CustomRegistrationForm, CustomLoginForm, IngredientForm, DishForm, DishIngredientFormSet, DietPlanForm, SubscriptionForm, PauseSubscriptionForm, ChangeDietForm
import traceback
from datetime import date, timedelta, datetime

from .shopping_utils import (
    get_week_ranges_for_subscriptions, 
    calculate_ingredients_for_week,
    format_week_display,
    get_week_number_in_month
)

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
                        return redirect('client_dashboard')
                except UserProfile.DoesNotExist:
                    UserProfile.objects.create(user=user, role='client')
                    return redirect('client_dashboard')
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
        'total_plans': DietPlan.objects.filter(is_active=True).count(),
        'active_subscriptions': 0,  # Dodamy później kiedy będą subskrypcje
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
# ZARZĄDZANIE PLANAMI DIETETYCZNYMI
# ==========================================

@login_required
def diet_plan_list(request):
    """Lista planów dietetycznych z paginacją i wyszukiwaniem"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Parametry z GET
    search = request.GET.get('search', '')
    per_page = request.GET.get('per_page', '25')
    show_inactive = request.GET.get('show_inactive', False)
    
    # Walidacja per_page
    if per_page not in ['10', '25', '50']:
        per_page = '25'
    
    # Bazowe query
    diet_plans = DietPlan.objects.all()
    
    # Filtrowanie nieaktywnych
    if not show_inactive:
        diet_plans = diet_plans.filter(is_active=True)
    
    # Wyszukiwanie
    if search:
        diet_plans = diet_plans.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    # Sortowanie
    diet_plans = diet_plans.order_by('name')
    
    # Paginacja
    paginator = Paginator(diet_plans, int(per_page))
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page_obj': page_obj,
        'search': search,
        'per_page': per_page,
        'show_inactive': show_inactive,
        'total_count': diet_plans.count(),
    }
    
    return render(request, 'management/diet_plans/list.html', context)

@login_required
def diet_plan_add(request):
    """Dodawanie nowego planu dietetycznego - wszystko na jednej stronie"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Pobierz wszystkie dania aktywne
    dishes = Dish.objects.filter(is_deleted=False).order_by('meal_type', 'name')
    
    # Przygotuj strukturę danych dla siatki
    days = [
        (1, 'Poniedziałek'), (2, 'Wtorek'), (3, 'Środa'), (4, 'Czwartek'),
        (5, 'Piątek'), (6, 'Sobota'), (7, 'Niedziela')
    ]
    
    meal_types = [
        ('breakfast', 'Śniadanie'),
        ('lunch', 'Obiad'),
        ('dinner', 'Kolacja')
    ]
    
    if request.method == 'POST':
        form = DietPlanForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Zapisz plan dietetyczny
                    diet_plan = form.save()
                    
                    # Zapisz meal_plans
                    meals_added = 0
                    for day_num, day_name in days:
                        for meal_type, meal_name in meal_types:
                            dish_id = request.POST.get(f'meal_{day_num}_{meal_type}')
                            if dish_id:
                                try:
                                    dish = Dish.objects.get(id=dish_id, is_deleted=False)
                                    MealPlan.objects.create(
                                        diet_plan=diet_plan,
                                        day_of_week=day_num,
                                        meal_type=meal_type,
                                        dish=dish
                                    )
                                    meals_added += 1
                                except Dish.DoesNotExist:
                                    continue
                    
                    messages.success(request, f'Plan "{diet_plan.name}" został utworzony z {meals_added} posiłkami.')
                    return redirect('diet_plan_list')
                    
            except Exception as e:
                messages.error(request, f'Wystąpił błąd podczas zapisywania: {str(e)}')
    else:
        form = DietPlanForm()
    
    # Przygotuj dane dla szablonu
    grid_data = []
    for day_num, day_name in days:
        day_meals = {meal_type: None for meal_type, _ in meal_types}
        grid_data.append({
            'day_num': day_num,
            'day_name': day_name,
            'meals': day_meals
        })
    
    context = {
        'form': form,
        'grid_data': grid_data,
        'meal_types': meal_types,
        'dishes': dishes,
        'days': days,
        'title': 'Dodaj plan dietetyczny',
        'submit_text': 'Stwórz plan dietetyczny'
    }
    
    return render(request, 'management/diet_plans/form.html', context)

@login_required
def diet_plan_edit(request, pk):
    """Edycja planu dietetycznego - wszystko na jednej stronie"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    diet_plan = get_object_or_404(DietPlan, pk=pk)
    
    # Pobierz wszystkie dania aktywne
    dishes = Dish.objects.filter(is_deleted=False).order_by('meal_type', 'name')
    
    # Pobierz istniejące meal_plans dla tego planu
    existing_meals = {}
    for meal_plan in MealPlan.objects.filter(diet_plan=diet_plan):
        key = f"{meal_plan.day_of_week}_{meal_plan.meal_type}"
        existing_meals[key] = meal_plan
    
    # Przygotuj strukturę danych dla siatki
    days = [
        (1, 'Poniedziałek'), (2, 'Wtorek'), (3, 'Środa'), (4, 'Czwartek'),
        (5, 'Piątek'), (6, 'Sobota'), (7, 'Niedziela')
    ]
    
    meal_types = [
        ('breakfast', 'Śniadanie'),
        ('lunch', 'Obiad'),
        ('dinner', 'Kolacja')
    ]
    
    if request.method == 'POST':
        form = DietPlanForm(request.POST, instance=diet_plan)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Zapisz plan dietetyczny
                    diet_plan = form.save()
                    
                    # Usuń wszystkie istniejące meal_plans dla tego planu
                    MealPlan.objects.filter(diet_plan=diet_plan).delete()
                    
                    # Zapisz nowe meal_plans
                    meals_added = 0
                    for day_num, day_name in days:
                        for meal_type, meal_name in meal_types:
                            dish_id = request.POST.get(f'meal_{day_num}_{meal_type}')
                            if dish_id:
                                try:
                                    dish = Dish.objects.get(id=dish_id, is_deleted=False)
                                    MealPlan.objects.create(
                                        diet_plan=diet_plan,
                                        day_of_week=day_num,
                                        meal_type=meal_type,
                                        dish=dish
                                    )
                                    meals_added += 1
                                except Dish.DoesNotExist:
                                    continue
                    
                    messages.success(request, f'Plan "{diet_plan.name}" został zaktualizowany z {meals_added} posiłkami.')
                    return redirect('diet_plan_list')
                    
            except Exception as e:
                messages.error(request, f'Wystąpił błąd podczas zapisywania: {str(e)}')
    else:
        form = DietPlanForm(instance=diet_plan)
    
    # Przygotuj dane dla szablonu
    grid_data = []
    for day_num, day_name in days:
        day_meals = {}
        for meal_type, meal_name in meal_types:
            key = f"{day_num}_{meal_type}"
            day_meals[meal_type] = existing_meals.get(key)
        grid_data.append({
            'day_num': day_num,
            'day_name': day_name,
            'meals': day_meals
        })
    
    context = {
        'form': form,
        'diet_plan': diet_plan,
        'grid_data': grid_data,
        'meal_types': meal_types,
        'dishes': dishes,
        'days': days,
        'title': f'Edytuj plan: {diet_plan.name}',
        'submit_text': 'Zaktualizuj plan dietetyczny'
    }
    
    return render(request, 'management/diet_plans/form.html', context)

@login_required
def diet_plan_delete(request, pk):
    """Deaktywacja planu dietetycznego"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    diet_plan = get_object_or_404(DietPlan, pk=pk)
    
    if request.method == 'POST':
        if diet_plan.is_active:
            # Deaktywuj plan
            diet_plan.is_active = False
            diet_plan.save()
            messages.success(request, f'Plan "{diet_plan.name}" został deaktywowany.')
        else:
            # Aktywuj plan
            diet_plan.is_active = True
            diet_plan.save()
            messages.success(request, f'Plan "{diet_plan.name}" został aktywowany.')
        
        return redirect('diet_plan_list')
    
    return render(request, 'management/diet_plans/confirm_delete.html', {
        'diet_plan': diet_plan
    })


def user_is_client(user):
    """Sprawdza czy użytkownik jest klientem"""
    try:
        return user.is_authenticated and user.userprofile.role == 'client'
    except UserProfile.DoesNotExist:
        return False

# ==========================================
# PANEL KLIENTA
# ==========================================

@login_required
def client_dashboard(request):
    """Dashboard dla klientów"""
    if not user_is_client(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Pobierz dane klienta
    try:
        loyalty_account = request.user.loyaltyaccount
    except:
        # Utwórz konto lojalnościowe jeśli nie istnieje
        from frontend.models import LoyaltyAccount
        loyalty_account = LoyaltyAccount.objects.create(
            user=request.user,
            points_balance=0,
            total_points_earned=0,
            loyalty_level='bronze'
        )
    
    # Pobierz aktywne subskrypcje
    active_subscriptions = Subscription.objects.filter(
        client=request.user,
        status__in=['active', 'paused']
    ).select_related('diet_plan').order_by('-created_at')
    
    # Pobierz ostatnie zamówienia/płatności
    recent_orders = Payment.objects.filter(
        subscription__client=request.user,
        status='completed'
    ).select_related('subscription__diet_plan').order_by('-created_at')[:5]
    
    # Pobierz nadchodzące dostawy (dla aktywnych subskrypcji)
    upcoming_deliveries = []
    for sub in active_subscriptions:
        # Symuluj najbliższą dostawę
        next_delivery = date.today() + timedelta(days=1)
        if next_delivery.weekday() == 6:  # Niedziela
            next_delivery += timedelta(days=1)
        upcoming_deliveries.append({
            'subscription': sub,
            'date': next_delivery,
            'time': '7:00-9:00'
        })
    
    # Generuj kod polecający
    referral_code = f'REF{request.user.id:05d}'
    
    # Sprawdź ile osób poleciłeś
    referrals_count = ReferralProgram.objects.filter(
        referrer=request.user,
        status='completed'
    ).count()
    
    # Oblicz wartość punktów (10 punktów = 1 zł)
    loyalty_value = loyalty_account.points_balance // 10
    
    # Oblicz postęp do następnego poziomu
    if loyalty_account.loyalty_level == 'bronze':
        next_level_points = 500
        progress_percentage = min(100, (loyalty_account.total_points_earned / 500) * 100)
    elif loyalty_account.loyalty_level == 'silver':
        next_level_points = 1000
        progress_percentage = min(100, ((loyalty_account.total_points_earned - 500) / 500) * 100)
    elif loyalty_account.loyalty_level == 'gold':
        next_level_points = 2000
        progress_percentage = min(100, ((loyalty_account.total_points_earned - 1000) / 1000) * 100)
    else:  # platinum
        next_level_points = 0
        progress_percentage = 100
    
    context = {
        'active_subscriptions': active_subscriptions,
        'recent_orders': recent_orders,
        'upcoming_deliveries': upcoming_deliveries,
        'loyalty_account': loyalty_account,
        'loyalty_points': loyalty_account.points_balance,
        'loyalty_level': loyalty_account.get_loyalty_level_display(),
        'loyalty_value': loyalty_value,
        'progress_percentage': int(progress_percentage),
        'next_level_points': next_level_points - loyalty_account.total_points_earned if next_level_points > 0 else 0,
        'referral_code': referral_code,
        'referrals_count': referrals_count,
        'total_saved': 0,  # TODO: Obliczać na podstawie wykorzystanych punktów
    }
    
    return render(request, 'client/dashboard.html', context)


@login_required
def client_profile(request):
    """Główny widok profilu klienta z wszystkimi sekcjami"""
    if not user_is_client(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Pobierz profil użytkownika
    try:
        profile = request.user.userprofile
    except UserProfile.DoesNotExist:
        # Utwórz profil jeśli nie istnieje
        profile = UserProfile.objects.create(
            user=request.user,
            role='client'
        )
    
    # Obsługa POST - aktualizacja różnych sekcji
    if request.method == 'POST':
        section = request.POST.get('section', 'personal-data')
        
        try:
            with transaction.atomic():
                if section == 'personal-data':
                    # Aktualizuj dane osobowe
                    user = request.user
                    user.first_name = request.POST.get('first_name', '').strip()
                    user.last_name = request.POST.get('last_name', '').strip()
                    
                    # Sprawdź czy email się zmienił i czy nie jest zajęty
                    new_email = request.POST.get('email', '').strip()
                    if new_email != user.email:
                        if User.objects.filter(email=new_email).exclude(pk=user.pk).exists():
                            messages.error(request, 'Adres email jest już używany przez inne konto.')
                            return redirect('client_profile')
                        user.email = new_email
                    
                    user.save()
                    
                    # Aktualizuj dane UserProfile
                    profile.phone = request.POST.get('phone', '').strip()
                    
                    # Data urodzenia
                    date_of_birth = request.POST.get('date_of_birth', '').strip()
                    if date_of_birth:
                        try:
                            from datetime import datetime
                            profile.date_of_birth = datetime.strptime(date_of_birth, '%Y-%m-%d').date()
                        except ValueError:
                            profile.date_of_birth = None
                    else:
                        profile.date_of_birth = None
                    
                    profile.save()
                    messages.success(request, 'Dane osobowe zostały zaktualizowane.')
                
                elif section == 'security':
                    # Zmiana hasła
                    old_password = request.POST.get('old_password')
                    new_password1 = request.POST.get('new_password1')
                    new_password2 = request.POST.get('new_password2')
                    
                    if not request.user.check_password(old_password):
                        messages.error(request, 'Nieprawidłowe obecne hasło.')
                        return redirect('client_profile')
                    
                    if new_password1 != new_password2:
                        messages.error(request, 'Nowe hasła nie są identyczne.')
                        return redirect('client_profile')
                    
                    if len(new_password1) < 8:
                        messages.error(request, 'Hasło musi mieć minimum 8 znaków.')
                        return redirect('client_profile')
                    
                    request.user.set_password(new_password1)
                    request.user.save()
                    update_session_auth_hash(request, request.user)  # Utrzymaj sesję
                    messages.success(request, 'Hasło zostało zmienione pomyślnie.')
                
                elif section == 'delivery':
                    # Aktualizuj szczegółowe pola adresu dostawy
                    profile.delivery_city = request.POST.get('city', '').strip()
                    profile.delivery_postal_code = request.POST.get('postal_code', '').strip()
                    profile.delivery_street = request.POST.get('street', '').strip()
                    profile.delivery_building_number = request.POST.get('building_number', '').strip()
                    profile.delivery_apartment_number = request.POST.get('apartment_number', '').strip()
                    profile.delivery_notes = request.POST.get('delivery_notes', '').strip()
                    
                    # Aktualizuj też stare pole address dla kompatybilności
                    if any([profile.delivery_city, profile.delivery_street, profile.delivery_building_number]):
                        address_parts = []
                        if profile.delivery_street and profile.delivery_building_number:
                            apartment = f"/{profile.delivery_apartment_number}" if profile.delivery_apartment_number else ""
                            address_parts.append(f"{profile.delivery_street} {profile.delivery_building_number}{apartment}")
                        if profile.delivery_postal_code and profile.delivery_city:
                            address_parts.append(f"{profile.delivery_postal_code} {profile.delivery_city}")
                        if profile.delivery_notes:
                            address_parts.append(f"Uwagi: {profile.delivery_notes}")
                        profile.address = ", ".join(address_parts)
                    
                    profile.save()
                    messages.success(request, 'Adres dostawy został zaktualizowany.')
                
                elif section == 'notifications':
                    # Zapisz ustawienia powiadomień
                    profile.newsletter = bool(request.POST.get('newsletter'))
                    profile.subscription_reminders = bool(request.POST.get('subscription_reminders'))
                    profile.delivery_notifications = bool(request.POST.get('delivery_notifications'))
                    profile.diet_change_confirmations = bool(request.POST.get('diet_change_confirmations'))
                    profile.promotional_offers = bool(request.POST.get('promotional_offers'))
                    
                    profile.save()
                    messages.success(request, 'Ustawienia powiadomień zostały zapisane.')
                
                elif section == 'delete-account':
                    # Usunięcie konta
                    confirmation = request.POST.get('confirmation', '').strip()
                    password = request.POST.get('password', '').strip()
                    
                    if confirmation != 'USUŃ KONTO':
                        messages.error(request, 'Wprowadź dokładnie "USUŃ KONTO" aby potwierdzić.')
                        return redirect('client_profile')
                    
                    if not request.user.check_password(password):
                        messages.error(request, 'Nieprawidłowe hasło.')
                        return redirect('client_profile')
                    
                    # Dezaktywuj konto (soft delete)
                    user = request.user
                    user.is_active = False
                    user.save()
                    
                    # Wyloguj użytkownika
                    logout(request)
                    
                    messages.success(request, 'Konto zostało usunięte. Dziękujemy za korzystanie z naszych usług.')
                    return redirect('home_page')
                
                return redirect('client_profile')
                
        except Exception as e:
            messages.error(request, f'Wystąpił błąd podczas zapisywania: {str(e)}')
    
    context = {
        'profile': profile,
    }
    
    return render(request, 'client/profile.html', context)


# ==========================================
# PRZEGLĄDANIE PLANÓW DIETETYCZNYCH (KLIENCI)
# ==========================================

def browse_diet_plans(request):
    """Lista dostępnych planów dietetycznych dla klientów"""
    
    # Parametry z GET
    sort_by = request.GET.get('sort', 'price_asc')  # price_asc, price_desc, name_asc, name_desc
    min_price = request.GET.get('min_price', '')
    max_price = request.GET.get('max_price', '')
    search = request.GET.get('search', '')
    
    # Pobierz tylko aktywne plany
    plans = DietPlan.objects.filter(is_active=True).prefetch_related(
        'mealplan_set__dish__dishingredient_set__ingredient'
    )
    
    # Wyszukiwanie
    if search:
        plans = plans.filter(
            Q(name__icontains=search) | Q(description__icontains=search)
        )
    
    # Filtrowanie po cenie
    if min_price:
        try:
            plans = plans.filter(weekly_price__gte=float(min_price))
        except ValueError:
            pass
    
    if max_price:
        try:
            plans = plans.filter(weekly_price__lte=float(max_price))
        except ValueError:
            pass
    
    # Sortowanie
    if sort_by == 'price_asc':
        plans = plans.order_by('weekly_price')
    elif sort_by == 'price_desc':
        plans = plans.order_by('-weekly_price')
    elif sort_by == 'name_asc':
        plans = plans.order_by('name')
    elif sort_by == 'name_desc':
        plans = plans.order_by('-name')
    else:
        plans = plans.order_by('weekly_price')
    
    # Wzbogać plany o dodatkowe informacje
    enriched_plans = []
    for plan in plans:
        # Policz posiłki w planie
        meal_count = plan.mealplan_set.count()
        
        # Oblicz średnie wartości odżywcze dzienne
        total_calories = 0
        total_protein = 0
        total_fat = 0
        total_cost = 0
        
        daily_meals = {}
        for meal_plan in plan.mealplan_set.all():
            day = meal_plan.day_of_week
            if day not in daily_meals:
                daily_meals[day] = []
            daily_meals[day].append(meal_plan.dish)
        
        # Oblicz średnie dla pełnych dni
        full_days_count = 0
        for day, dishes in daily_meals.items():
            if len(dishes) == 3:  # Pełny dzień (3 posiłki)
                full_days_count += 1
                for dish in dishes:
                    total_calories += dish.total_calories
                    total_protein += dish.total_protein
                    total_fat += dish.total_fat
                    total_cost += dish.total_cost
        
        avg_calories = (float(total_calories) / full_days_count) if full_days_count > 0 else 0
        avg_protein = (float(total_protein) / full_days_count) if full_days_count > 0 else 0
        avg_fat = (float(total_fat) / full_days_count) if full_days_count > 0 else 0
        weekly_food_cost = float(total_cost) * (7 / full_days_count) if full_days_count > 0 else 0
        
        # Znajdź alergeny w planie
        allergens_set = set()
        for meal_plan in plan.mealplan_set.all():
            if meal_plan.dish.allergens:
                dish_allergens = [a.strip() for a in meal_plan.dish.allergens.split(',') if a.strip()]
                allergens_set.update(dish_allergens)
        
        enriched_plans.append({
            'plan': plan,
            'meal_count': meal_count,
            'avg_calories': round(avg_calories),
            'avg_protein': round(avg_protein, 1),
            'avg_fat': round(avg_fat, 1),
            'weekly_food_cost': round(weekly_food_cost, 2),
            'margin': round(float(plan.weekly_price) - weekly_food_cost, 2),
            'allergens': sorted(list(allergens_set)),
            'completion_percentage': round((meal_count / 21) * 100),
        })
    
    context = {
        'enriched_plans': enriched_plans,
        'sort_by': sort_by,
        'min_price': min_price,
        'max_price': max_price,
        'search': search,
        'total_count': len(enriched_plans),
    }
    
    return render(request, 'plans/browse.html', context)


def diet_plan_detail(request, pk):
    """Szczegóły planu dietetycznego z pełną siatką posiłków"""
    
    plan = get_object_or_404(DietPlan, pk=pk, is_active=True)
    
    # Pobierz wszystkie meal_plans dla tego planu
    meal_plans = MealPlan.objects.filter(diet_plan=plan).select_related('dish').prefetch_related(
        'dish__dishingredient_set__ingredient'
    )
    
    # Organizuj dane w siatkę 7x3
    days = [
        (1, 'Poniedziałek'), (2, 'Wtorek'), (3, 'Środa'), (4, 'Czwartek'),
        (5, 'Piątek'), (6, 'Sobota'), (7, 'Niedziela')
    ]
    
    meal_types = [
        ('breakfast', 'Śniadanie'),
        ('lunch', 'Obiad'),
        ('dinner', 'Kolacja')
    ]
    
    # Stwórz mapę meal_plans
    meal_grid = {}
    for meal_plan in meal_plans:
        key = f"{meal_plan.day_of_week}_{meal_plan.meal_type}"
        meal_grid[key] = meal_plan
    
    # Przygotuj dane dla szablonu
    grid_data = []
    for day_num, day_name in days:
        day_meals = {}
        for meal_type, meal_name in meal_types:
            key = f"{day_num}_{meal_type}"
            day_meals[meal_type] = meal_grid.get(key)
        grid_data.append({
            'day_num': day_num,
            'day_name': day_name,
            'meals': day_meals
        })
    
    # Oblicz statystyki planu
    total_calories = 0
    total_protein = 0
    total_fat = 0
    total_cost = 0
    allergens_set = set()
    
    for meal_plan in meal_plans:
        dish = meal_plan.dish
        total_calories += dish.total_calories
        total_protein += dish.total_protein
        total_fat += dish.total_fat
        total_cost += dish.total_cost
        
        if dish.allergens:
            dish_allergens = [a.strip() for a in dish.allergens.split(',') if a.strip()]
            allergens_set.update(dish_allergens)
    
    # Oblicz średnie dzienne (dla 7 dni)
    avg_daily_calories = total_calories / 7 if meal_plans.count() > 0 else 0
    avg_daily_protein = total_protein / 7 if meal_plans.count() > 0 else 0
    avg_daily_fat = total_fat / 7 if meal_plans.count() > 0 else 0
    
    # Znajdź podobne plany (do rekomendacji)
    similar_plans = DietPlan.objects.filter(
        is_active=True
    ).exclude(pk=plan.pk).order_by('weekly_price')[:3]
    
    context = {
        'plan': plan,
        'grid_data': grid_data,
        'meal_types': meal_types,
        'days': days,
        'meal_count': meal_plans.count(),
        'completion_percentage': round((meal_plans.count() / 21) * 100),
        'avg_daily_calories': round(avg_daily_calories),
        'avg_daily_protein': round(avg_daily_protein, 1),
        'avg_daily_fat': round(avg_daily_fat, 1),
        'weekly_cost': round(total_cost, 2),
        'allergens': sorted(list(allergens_set)),
        'similar_plans': similar_plans,
    }
    
    return render(request, 'plans/detail.html', context)


def compare_diet_plans(request):
    """Porównanie wybranych planów dietetycznych"""
    
    # Pobierz ID planów z GET parametrów
    plan_ids = request.GET.getlist('plans')
    
    # Ogranicz do maksymalnie 3 planów
    plan_ids = plan_ids[:3]
    
    if not plan_ids:
        messages.error(request, 'Wybierz plany do porównania.')
        return redirect('browse_diet_plans')
    
    # Pobierz plany
    plans = DietPlan.objects.filter(
        id__in=plan_ids, 
        is_active=True
    ).prefetch_related('mealplan_set__dish__dishingredient_set__ingredient')
    
    if not plans.exists():
        messages.error(request, 'Nie znaleziono wybranych planów.')
        return redirect('browse_diet_plans')
    
    # Przygotuj dane porównawcze
    comparison_data = []
    for plan in plans:
        # Oblicz statystyki
        meal_plans = plan.mealplan_set.all()
        
        total_calories = sum(float(mp.dish.total_calories) for mp in meal_plans)
        total_protein = sum(float(mp.dish.total_protein) for mp in meal_plans)
        total_fat = sum(float(mp.dish.total_fat) for mp in meal_plans)
        total_cost = sum(float(mp.dish.total_cost) for mp in meal_plans)
        
        # Znajdź alergeny
        allergens_set = set()
        for meal_plan in meal_plans:
            if meal_plan.dish.allergens:
                dish_allergens = [a.strip() for a in meal_plan.dish.allergens.split(',') if a.strip()]
                allergens_set.update(dish_allergens)
        
        # Policz posiłki według typu
        meal_type_counts = {'breakfast': 0, 'lunch': 0, 'dinner': 0}
        for meal_plan in meal_plans:
            meal_type_counts[meal_plan.meal_type] += 1
        
        comparison_data.append({
            'plan': plan,
            'meal_count': meal_plans.count(),
            'completion_percentage': round((meal_plans.count() / 21) * 100),
            'avg_daily_calories': round(total_calories / 7) if meal_plans.count() > 0 else 0,
            'avg_daily_protein': round(total_protein / 7, 1) if meal_plans.count() > 0 else 0,
            'avg_daily_fat': round(total_fat / 7, 1) if meal_plans.count() > 0 else 0,
            'weekly_cost': round(total_cost, 2),
            'allergens': sorted(list(allergens_set)),
            'meal_type_counts': meal_type_counts,
        })
    
    context = {
        'comparison_data': comparison_data,
        'plan_count': len(comparison_data),
    }
    
    return render(request, 'plans/compare.html', context)


@require_GET
def dish_detail_api(request, dish_id):
    """API endpoint do pobierania szczegółów dania"""
    try:
        dish = Dish.objects.select_related().prefetch_related(
            'dishingredient_set__ingredient'
        ).get(id=dish_id, is_deleted=False)
        
        # Przygotuj dane składników
        ingredients_data = []
        for dish_ingredient in dish.dishingredient_set.all():
            ingredient = dish_ingredient.ingredient
            quantity = float(dish_ingredient.quantity_grams)
            
            # Oblicz wartości odżywcze dla tej ilości
            calories = (float(ingredient.calories_per_100g) * quantity) / 100
            protein = (float(ingredient.protein_per_100g) * quantity) / 100
            fat = (float(ingredient.fat_per_100g) * quantity) / 100
            cost = (float(ingredient.price_per_100g) * quantity) / 100
            
            ingredients_data.append({
                'name': ingredient.name,
                'quantity_grams': quantity,
                'calories': round(calories, 1),
                'protein': round(protein, 1),
                'fat': round(fat, 1),
                'cost': round(cost, 2),
            })
        
        # Przygotuj alergeny
        allergens = []
        if dish.allergens:
            allergens = [a.strip() for a in dish.allergens.split(',') if a.strip()]
        
        data = {
            'id': dish.id,
            'name': dish.name,
            'description': dish.description,
            'meal_type': dish.get_meal_type_display(),
            'allergens': allergens,
            'image_url': dish.image.url if dish.image else None,
            'total_calories': round(float(dish.total_calories), 1),
            'total_protein': round(float(dish.total_protein), 1),
            'total_fat': round(float(dish.total_fat), 1),
            'total_cost': round(float(dish.total_cost), 2),
            'ingredients': ingredients_data,
        }
        
        return JsonResponse(data)
        
    except Dish.DoesNotExist:
        return JsonResponse({'error': 'Danie nie znalezione'}, status=404)


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

# ==========================================
# MODUŁ ZAMÓWIEŃ I SUBSKRYPCJI
# ==========================================

@login_required
def subscription_list(request):
    """Lista subskrypcji klienta"""
    if not user_is_client(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Pobierz subskrypcje użytkownika
    subscriptions = Subscription.objects.filter(
        client=request.user
    ).select_related('diet_plan').order_by('-created_at')
    
    # Podziel na aktywne i historyczne
    active_subscriptions = []
    historical_subscriptions = []
    
    for sub in subscriptions:
        if sub.status in ['active', 'paused']:
            active_subscriptions.append(sub)
        else:
            historical_subscriptions.append(sub)
    
    context = {
        'active_subscriptions': active_subscriptions,
        'historical_subscriptions': historical_subscriptions,
    }
    
    return render(request, 'client/subscriptions/list.html', context)


@login_required
def subscription_detail(request, subscription_id):
    """Szczegóły subskrypcji"""
    if not user_is_client(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    subscription = get_object_or_404(
        Subscription, 
        id=subscription_id, 
        client=request.user
    )
    
    # Pobierz historię zmian diety
    diet_changes = DietChange.objects.filter(
        subscription=subscription
    ).order_by('-created_at')
    
    # Pobierz nadchodzące dostawy
    upcoming_deliveries = Delivery.objects.filter(
        subscription=subscription,
        delivery_date__gte=date.today(),
        status__in=['preparing', 'ready']
    ).order_by('delivery_date')[:5]
    
    # Pobierz ostatnie dostawy
    recent_deliveries = Delivery.objects.filter(
        subscription=subscription,
        status='delivered'
    ).order_by('-delivery_date')[:5]
    
    context = {
        'subscription': subscription,
        'diet_changes': diet_changes,
        'upcoming_deliveries': upcoming_deliveries,
        'recent_deliveries': recent_deliveries,
    }
    
    return render(request, 'client/subscriptions/detail.html', context)


@login_required
def subscription_create(request, plan_id):
    """Tworzenie nowej subskrypcji"""
    if not user_is_client(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    diet_plan = get_object_or_404(DietPlan, id=plan_id, is_active=True)
    
    if request.method == 'POST':
        form = SubscriptionForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Oblicz daty i cenę
                    duration = form.cleaned_data['duration']
                    start_date = form.cleaned_data['start_date']
                    
                    if duration == 'week':
                        end_date = start_date + timedelta(days=7)
                        total_amount = diet_plan.weekly_price
                    elif duration == 'month':
                        end_date = start_date + timedelta(days=30)
                        total_amount = diet_plan.monthly_price
                    else:  # year
                        end_date = start_date + timedelta(days=365)
                        total_amount = diet_plan.yearly_price
                    
                    # Twórz subskrypcję
                    subscription = Subscription.objects.create(
                        client=request.user,
                        diet_plan=diet_plan,
                        duration=duration,
                        status='pending',
                        start_date=start_date,
                        end_date=end_date,
                        total_amount=total_amount,
                        delivery_address=form.cleaned_data['delivery_address'],
                        delivery_notes=form.cleaned_data['delivery_notes']
                    )
                    
                    # TODO: Integracja z Stripe dla płatności
                    # Na razie symuluj płatność
                    subscription.status = 'active'
                    subscription.save()
                    
                    # Dodaj punkty lojalnościowe (1 punkt = 1 zł)
                    try:
                        loyalty_account = request.user.loyaltyaccount
                        loyalty_account.add_points(
                            points=int(total_amount),
                            transaction_type='purchase',
                            description=f'Zakup subskrypcji: {diet_plan.name} ({duration})',
                            related_order=subscription
                        )
                    except:
                        pass
                    
                    messages.success(request, 'Subskrypcja została utworzona pomyślnie!')
                    return redirect('subscription_detail', subscription_id=subscription.id)
                    
            except Exception as e:
                messages.error(request, f'Wystąpił błąd podczas tworzenia subskrypcji: {str(e)}')
    else:
        # Ustaw domyślną datę rozpoczęcia (najbliższy poniedziałek)
        today = date.today()
        days_until_monday = (7 - today.weekday()) % 7
        if days_until_monday < 2:  # Jeśli to weekend, weź następny poniedziałek
            days_until_monday += 7
        default_start_date = today + timedelta(days=days_until_monday)
        
        form = SubscriptionForm(
            initial={'diet_plan': diet_plan, 'start_date': default_start_date},
            user=request.user
        )
    
    context = {
        'form': form,
        'diet_plan': diet_plan,
    }
    
    return render(request, 'client/subscriptions/create.html', context)


@login_required
def subscription_pause(request, subscription_id):
    """Pauzowanie subskrypcji"""
    if not user_is_client(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    subscription = get_object_or_404(
        Subscription, 
        id=subscription_id, 
        client=request.user,
        status='active'
    )
    
    if request.method == 'POST':
        form = PauseSubscriptionForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    pause_start = form.cleaned_data['pause_start_date']
                    pause_end = form.cleaned_data['pause_end_date']
                    
                    # Sprawdź czy daty pauzy mieszczą się w okresie subskrypcji
                    if pause_start > subscription.end_date:
                        messages.error(request, 'Data rozpoczęcia pauzy wykracza poza okres subskrypcji.')
                        return redirect('subscription_detail', subscription_id=subscription.id)
                    
                    # Ustaw status na wstrzymany
                    subscription.status = 'paused'
                    
                    # Przedłuż subskrypcję o dni pauzy
                    pause_days = (pause_end - pause_start).days + 1
                    subscription.end_date += timedelta(days=pause_days)
                    
                    subscription.save()
                    
                    # Zapisz informację o pauzie (można dodać model PauseHistory jeśli potrzebny)
                    messages.success(request, f'Subskrypcja została wstrzymana od {pause_start.strftime("%d.%m.%Y")} do {pause_end.strftime("%d.%m.%Y")}.')
                    
                    # Anuluj dostawy w okresie pauzy
                    Delivery.objects.filter(
                        subscription=subscription,
                        delivery_date__gte=pause_start,
                        delivery_date__lte=pause_end,
                        status__in=['preparing', 'ready']
                    ).update(status='cancelled')
                    
                    return redirect('subscription_detail', subscription_id=subscription.id)
                    
            except Exception as e:
                messages.error(request, f'Wystąpił błąd podczas pauzowania subskrypcji: {str(e)}')
    else:
        # Ustaw domyślną datę rozpoczęcia pauzy na jutro
        form = PauseSubscriptionForm(initial={
            'pause_start_date': date.today() + timedelta(days=1)
        })
    
    context = {
        'form': form,
        'subscription': subscription,
    }
    
    return render(request, 'client/subscriptions/pause.html', context)


@login_required
def subscription_cancel(request, subscription_id):
    """Anulowanie subskrypcji"""
    if not user_is_client(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    subscription = get_object_or_404(
        Subscription, 
        id=subscription_id, 
        client=request.user,
        status__in=['active', 'paused']
    )
    
    if request.method == 'POST':
        # TODO: Oblicz zwrot proporcjonalny
        subscription.status = 'cancelled'
        subscription.save()
        
        messages.success(request, 'Subskrypcja została anulowana.')
        return redirect('subscription_list')
    
    # Oblicz potencjalny zwrot
    days_used = (date.today() - subscription.start_date).days
    total_days = (subscription.end_date - subscription.start_date).days
    days_remaining = max(0, total_days - days_used)
    refund_amount = (subscription.total_amount / total_days) * days_remaining
    
    context = {
        'subscription': subscription,
        'days_remaining': days_remaining,
        'refund_amount': round(refund_amount, 2),
    }
    
    return render(request, 'client/subscriptions/cancel.html', context)


@login_required
def diet_change(request, subscription_id):
    """Zmiana planu dietetycznego"""
    if not user_is_client(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    subscription = get_object_or_404(
        Subscription, 
        id=subscription_id, 
        client=request.user,
        status='active'
    )
    
    # Sprawdź czy można zmienić dietę
    if not subscription.can_change_diet():
        messages.error(request, 'Osiągnięto limit zmian diety w tym miesiącu (max. 2).')
        return redirect('subscription_detail', subscription_id=subscription.id)
    
    if request.method == 'POST':
        form = ChangeDietForm(request.POST, subscription=subscription)
        if form.is_valid():
            try:
                with transaction.atomic():
                    new_plan = form.cleaned_data['new_diet_plan']
                    change_date = form.cleaned_data['change_date']
                    
                    # Znajdź najbliższy poniedziałek
                    days_until_monday = (7 - change_date.weekday()) % 7
                    if days_until_monday == 0:  # Jeśli to już poniedziałek
                        effective_date = change_date
                    else:
                        effective_date = change_date + timedelta(days=days_until_monday)
                    
                    # Oblicz korektę ceny
                    days_remaining = (subscription.end_date - effective_date).days
                    total_days = (subscription.end_date - subscription.start_date).days
                    
                    # Proporcjonalny koszt starej i nowej diety
                    old_daily_rate = subscription.total_amount / total_days
                    new_daily_rate = _calculate_daily_rate(new_plan, subscription.duration)
                    
                    price_adjustment = (new_daily_rate - old_daily_rate) * days_remaining
                    
                    # Utwórz rekord zmiany
                    diet_change = DietChange.objects.create(
                        subscription=subscription,
                        old_plan=subscription.diet_plan,
                        new_plan=new_plan,
                        change_date=effective_date,
                        reason=form.cleaned_data.get('reason', ''),
                        price_adjustment=price_adjustment,
                        status='pending'
                    )
                    
                    # Zaktualizuj subskrypcję
                    subscription.diet_plan = new_plan
                    subscription.diet_changes_count += 1
                    subscription.save()
                    
                    # Oznacz zmianę jako potwierdzoną
                    diet_change.status = 'confirmed'
                    diet_change.save()
                    
                    messages.success(request, f'Zmiana diety została zaplanowana na {effective_date.strftime("%d.%m.%Y")}.')
                    
                    # Jeśli dopłata, przekieruj do płatności
                    if price_adjustment > 0:
                        messages.info(request, f'Do dopłaty: {price_adjustment:.2f} zł')
                        # TODO: Przekieruj do płatności
                    elif price_adjustment < 0:
                        messages.info(request, f'Zwrot: {abs(price_adjustment):.2f} zł zostanie przelany na Twoje konto.')
                    
                    return redirect('subscription_detail', subscription_id=subscription.id)
                    
            except Exception as e:
                messages.error(request, f'Wystąpił błąd podczas zmiany diety: {str(e)}')
    else:
        form = ChangeDietForm(subscription=subscription)
    
    # Pobierz dostępne plany z cenami
    available_plans = []
    for plan in form.fields['new_diet_plan'].queryset:
        daily_rate = _calculate_daily_rate(plan, subscription.duration)
        current_daily_rate = subscription.total_amount / (subscription.end_date - subscription.start_date).days
        price_diff = daily_rate - current_daily_rate
        
        available_plans.append({
            'plan': plan,
            'daily_rate': daily_rate,
            'price_difference': price_diff,
        })
    
    context = {
        'form': form,
        'subscription': subscription,
        'available_plans': available_plans,
        'changes_remaining': 2 - subscription.diet_changes_count,
    }
    
    return render(request, 'client/subscriptions/diet_change.html', context)

@login_required
def client_payments(request):
    """Historia płatności klienta"""
    if not user_is_client(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Pobierz wszystkie płatności użytkownika
    payments = Payment.objects.filter(
        subscription__client=request.user
    ).select_related('subscription__diet_plan').order_by('-created_at')
    
    # Paginacja
    paginator = Paginator(payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Oblicz statystyki
    total_spent = payments.filter(status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    context = {
        'page_obj': page_obj,
        'total_spent': total_spent,
        'payments_count': payments.count(),
    }
    
    return render(request, 'client/payments/list.html', context)

def _calculate_daily_rate(plan, duration):
    """Calculate daily rate for a diet plan and duration ('week', 'month', 'year')."""
    if duration == 'week':
        return float(plan.weekly_price) / 7
    elif duration == 'month':
        return float(plan.monthly_price) / 30
    elif duration == 'year':
        return float(plan.yearly_price) / 365
    else:
        return 0

@login_required
def shopping_list_overview(request):
    """
    Strona z przegldem wszystkich tygodni dla ktorych trzeba generowac listy zakupow
    """
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Pobierz zakresy tygodni z aktywnymi subskrypcjami
    week_ranges = get_week_ranges_for_subscriptions()
    
    # Przygotuj dane dla szablonu
    weeks_data = []
    for week_start, week_end in week_ranges:
        week_number = get_week_number_in_month(week_start)
        month_year = week_start.strftime('%B %Y')
        
        # Przelicz na polski miesiac
        polish_months = {
            'January': 'Styczeń', 'February': 'Luty', 'March': 'Marzec',
            'April': 'Kwiecień', 'May': 'Maj', 'June': 'Czerwiec',
            'July': 'Lipiec', 'August': 'Sierpień', 'September': 'Wrzesień',
            'October': 'Październik', 'November': 'Listopad', 'December': 'Grudzień'
        }
        
        english_month = week_start.strftime('%B')
        polish_month = polish_months.get(english_month, english_month)
        month_year_polish = f"{polish_month} {week_start.year}"
        
        weeks_data.append({
            'week_start': week_start,
            'week_end': week_end,
            'week_display': format_week_display(week_start, week_end),
            'week_number': week_number,
            'month_year': month_year_polish,
        })
    
    context = {
        'weeks_data': weeks_data,
        'total_weeks': len(weeks_data),
    }
    
    return render(request, 'management/shopping/overview.html', context)

@login_required
def shopping_list_preview(request, year, month, day):
    """
    Podglad listy zakupow przed wygenerowaniem PDF
    """
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    try:
        week_start = datetime(year, month, day).date()
    except ValueError:
        messages.error(request, 'Nieprawidłowa data.')
        return redirect('shopping_list_overview')
    
    week_end = week_start + timedelta(days=6)
    
    # Oblicz skladniki
    ingredients_data = calculate_ingredients_for_week(week_start, week_end)
    
    # Przygotuj dane dla szablonu
    sorted_ingredients = []
    if ingredients_data:
        for item in sorted(ingredients_data.values(), key=lambda x: x['ingredient'].name):
            item['total_kilos'] = item['total_grams'] / 1000
            sorted_ingredients.append(item)
    
    total_cost = sum(item['total_cost'] for item in ingredients_data.values())
    
    context = {
        'week_start': week_start,
        'week_end': week_end,
        'week_display': format_week_display(week_start, week_end),
        'ingredients': sorted_ingredients,
        'total_cost': total_cost,
        'ingredients_count': len(sorted_ingredients),
    }
    
    return render(request, 'management/shopping/preview.html', context)