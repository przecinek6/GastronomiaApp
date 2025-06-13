# frontend/shopping_utils.py
from datetime import datetime, timedelta
from django.db.models import Sum
from collections import defaultdict
from .models import Subscription, MealPlan, DishIngredient


def get_monday_of_week(date):
    """Zwraca poniedzialek tygodnia dla podanej daty"""
    days_ahead = date.weekday()
    return date - timedelta(days=days_ahead)


def get_week_ranges_for_subscriptions():
    """
    Zwraca liste zakresow tygodni dla ktorych sa aktywne subskrypcje
    Format: [(start_date, end_date), ...]
    """
    # Pobierz wszystkie aktywne subskrypcje
    active_subscriptions = Subscription.objects.filter(
        status__in=['active', 'pending']
    ).values('start_date', 'end_date')
    
    if not active_subscriptions:
        return []
    
    # Znajdz najwczesniejsza i najpozniejsza date
    earliest_date = min(sub['start_date'] for sub in active_subscriptions)
    latest_date = max(sub['end_date'] for sub in active_subscriptions)
    
    # Znajdz poniedzialek tygodnia dla najwczesniejszej daty
    current_monday = get_monday_of_week(earliest_date)
    week_ranges = []
    
    while current_monday <= latest_date:
        week_end = current_monday + timedelta(days=6)  # niedziela
        
        # Sprawdz czy w tym tygodniu sa jakies aktywne subskrypcje
        has_active_subs = any(
            sub['start_date'] <= week_end and sub['end_date'] >= current_monday
            for sub in active_subscriptions
        )
        
        if has_active_subs:
            week_ranges.append((current_monday, week_end))
        
        current_monday += timedelta(days=7)
    
    return week_ranges


def calculate_ingredients_for_week(week_start, week_end):
    """
    Oblicza ilosc skladnikow potrzebnych dla danego tygodnia
    Zwraca slownik: {ingredient_id: {'ingredient': obj, 'total_grams': float, 'total_cost': float}}
    """
    # Pobierz wszystkie aktywne subskrypcje w tym tygodniu
    active_subscriptions = Subscription.objects.filter(
        status__in=['active', 'pending'],
        start_date__lte=week_end,
        end_date__gte=week_start
    ).select_related('diet_plan')
    
    if not active_subscriptions:
        return {}
    
    ingredients_summary = defaultdict(lambda: {
        'ingredient': None,
        'total_grams': 0,
        'total_cost': 0
    })
    
    for subscription in active_subscriptions:
        diet_plan = subscription.diet_plan
        
        # Oblicz ile dni w tym tygodniu obejmuje subskrypcja
        sub_start_in_week = max(subscription.start_date, week_start)
        sub_end_in_week = min(subscription.end_date, week_end)
        
        if sub_start_in_week <= sub_end_in_week:
            # Pobierz wszystkie posilki dla tego planu dietetycznego
            meal_plans = MealPlan.objects.filter(
                diet_plan=diet_plan
            ).select_related('dish').prefetch_related(
                'dish__dishingredient_set__ingredient'
            )
            
            # Dla kazdego dnia tygodnia (1-7) i kazdego posilku
            for day_of_week in range(1, 8):
                # Sprawdz czy ten dzien jest w zakresie subskrypcji
                current_date = week_start + timedelta(days=day_of_week-1)
                if sub_start_in_week <= current_date <= sub_end_in_week:
                    
                    # Pobierz posilki dla tego dnia
                    day_meals = meal_plans.filter(day_of_week=day_of_week)
                    
                    for meal_plan in day_meals:
                        dish = meal_plan.dish
                        dish_ingredients = dish.dishingredient_set.all()
                        
                        for dish_ingredient in dish_ingredients:
                            ingredient = dish_ingredient.ingredient
                            quantity_grams = float(dish_ingredient.quantity_grams)
                            cost = quantity_grams * float(ingredient.price_per_100g) / 100
                            
                            ingredients_summary[ingredient.id]['ingredient'] = ingredient
                            ingredients_summary[ingredient.id]['total_grams'] += quantity_grams
                            ingredients_summary[ingredient.id]['total_cost'] += cost
    
    return dict(ingredients_summary)


def format_week_display(week_start, week_end):
    """Formatuje zakres tygodnia do wyswietlenia"""
    return f"{week_start.strftime('%d.%m.%Y')} - {week_end.strftime('%d.%m.%Y')}"


def get_week_number_in_month(date):
    """Zwraca numer tygodnia w miesiacu"""
    first_day_of_month = date.replace(day=1)
    first_monday = get_monday_of_week(first_day_of_month)
    
    if first_monday.month < date.month:
        first_monday += timedelta(days=7)
    
    weeks_diff = (get_monday_of_week(date) - first_monday).days // 7
    return weeks_diff + 1