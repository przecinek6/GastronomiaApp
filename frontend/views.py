from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from frontend.models import UserProfile, Ingredient, Dish, DishIngredient, DietPlan, MealPlan
from frontend.forms import CustomRegistrationForm, CustomLoginForm, IngredientForm, DishForm, DishIngredientFormSet, DietPlanForm
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
    
    # Podstawowe statystyki (na razie mock data)
    context = {
        'active_subscriptions': 0,  # Dodamy później gdy będą subskrypcje
        'loyalty_points': loyalty_account.points_balance,
        'loyalty_level': loyalty_account.get_loyalty_level_display(),
        'loyalty_value': loyalty_account.points_balance // 10,  # 10 punktów = 1 zł
        'total_orders': 0,  # Dodamy później
        'total_saved': 0,  # Dodamy później
        'referral_code': f'USER{request.user.id:03d}',  # Prosty kod polecający
    }
    
    return render(request, 'client/dashboard.html', context)


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
    
    return render(request, 'client/browse_plans.html', context)


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
    
    return render(request, 'client/plan_detail.html', context)


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
    
    return render(request, 'client/compare_plans.html', context)


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