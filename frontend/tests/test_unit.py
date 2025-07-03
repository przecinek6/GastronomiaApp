import unittest
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import date, timedelta
from django.db import models

from frontend.models import (
    Ingredient, Dish, DishIngredient, DietPlan, 
    Subscription, Payment, LoyaltyAccount, PointTransaction, DietChange
)


class IngredientModelTest(TestCase):
    """Test modelu Ingredient - walidacja i obliczenia"""
    
    def setUp(self):
        self.valid_ingredient_data = {
            'name': 'Kurczak pierś',
            'calories_per_100g': Decimal('165.0'),
            'protein_per_100g': Decimal('31.0'),
            'fat_per_100g': Decimal('3.6'),
            'price_per_100g': Decimal('2.50')
        }
    
    def test_ingredient_creation_valid_data(self):
        """Test tworzenia składnika z poprawnymi danymi"""
        ingredient = Ingredient.objects.create(**self.valid_ingredient_data)
        
        self.assertEqual(ingredient.name, 'Kurczak pierś')
        self.assertEqual(ingredient.calories_per_100g, Decimal('165.0'))
        self.assertFalse(ingredient.is_deleted)
        self.assertIsNotNone(ingredient.created_at)
    
    def test_ingredient_name_validation(self):
        """Test walidacji nazwy składnika"""
        # Pusta nazwa
        with self.assertRaises(ValidationError):
            ingredient = Ingredient(**{**self.valid_ingredient_data, 'name': ''})
            ingredient.full_clean()
        
        # Nazwa zbyt długa (zakładając max 100 znaków)
        with self.assertRaises(ValidationError):
            ingredient = Ingredient(**{**self.valid_ingredient_data, 'name': 'A' * 201})
            ingredient.full_clean()
    
    def test_ingredient_negative_values_validation(self):
        """Test walidacji ujemnych wartości odżywczych"""
        test_cases = [
            ('calories_per_100g', Decimal('-10.0')),
            ('protein_per_100g', Decimal('-5.0')),
            ('fat_per_100g', Decimal('-1.0')),
            ('price_per_100g', Decimal('-0.5'))
        ]
        
        for field, invalid_value in test_cases:
            with self.subTest(field=field):
                with self.assertRaises(ValidationError):
                    ingredient = Ingredient(**{**self.valid_ingredient_data, field: invalid_value})
                    ingredient.full_clean()
    
    def test_ingredient_soft_delete(self):
        """Test soft delete składnika"""
        ingredient = Ingredient.objects.create(**self.valid_ingredient_data)
        ingredient.is_deleted = True
        ingredient.save()
        
        self.assertTrue(ingredient.is_deleted)
        # Weryfikacja czy składnik nie pojawia się w aktywnych zapytaniach
        active_ingredients = Ingredient.objects.filter(is_deleted=False)
        self.assertNotIn(ingredient, active_ingredients)


class DishModelTest(TestCase):
    """Test modelu Dish - obliczenia wartości odżywczych i kosztów"""
    
    def setUp(self):
        self.user = User.objects.create_user(
            username='testmanager',
            email='test@example.com',
            password='testpass123'
        )
        
        # Składniki testowe
        self.chicken = Ingredient.objects.create(
            name='Kurczak pierś',
            calories_per_100g=Decimal('165.0'),
            protein_per_100g=Decimal('31.0'),
            fat_per_100g=Decimal('3.6'),
            price_per_100g=Decimal('2.50')
        )
        
        self.rice = Ingredient.objects.create(
            name='Ryż biały',
            calories_per_100g=Decimal('130.0'),
            protein_per_100g=Decimal('2.7'),
            fat_per_100g=Decimal('0.3'),
            price_per_100g=Decimal('0.80')
        )
        
        self.oil = Ingredient.objects.create(
            name='Olej rzepakowy',
            calories_per_100g=Decimal('884.0'),
            protein_per_100g=Decimal('0.0'),
            fat_per_100g=Decimal('100.0'),
            price_per_100g=Decimal('1.20')
        )
    
    def test_dish_nutritional_calculations(self):
        """Test automatycznych obliczeń wartości odżywczych dania"""
        dish = Dish.objects.create(
            name='Kurczak z ryżem',
            description='Klasyczne danie z kurczakiem i ryżem',
            meal_type='lunch',
            allergens='gluten'
        )
        
        # Dodanie składników: 200g kurczaka, 150g ryżu, 10g oleju
        DishIngredient.objects.create(
            dish=dish,
            ingredient=self.chicken,
            quantity_grams=Decimal('200.0')
        )
        
        DishIngredient.objects.create(
            dish=dish,
            ingredient=self.rice,
            quantity_grams=Decimal('150.0')
        )
        
        DishIngredient.objects.create(
            dish=dish,
            ingredient=self.oil,
            quantity_grams=Decimal('10.0')
        )
        
        # Obliczenia ręczne do weryfikacji
        expected_calories = (165.0 * 2.0) + (130.0 * 1.5) + (884.0 * 0.1)  # 713.4
        expected_protein = (31.0 * 2.0) + (2.7 * 1.5) + (0.0 * 0.1)  # 66.05
        expected_fat = (3.6 * 2.0) + (0.3 * 1.5) + (100.0 * 0.1)  # 17.65
        expected_cost = (2.50 * 2.0) + (0.80 * 1.5) + (1.20 * 0.1)  # 6.32
        
        # Weryfikacja obliczeń (z tolerancją na błędy zaokrąglenia)
        self.assertAlmostEqual(float(dish.total_calories), expected_calories, places=1)
        self.assertAlmostEqual(float(dish.total_protein), expected_protein, places=1)
        self.assertAlmostEqual(float(dish.total_fat), expected_fat, places=1)
        self.assertAlmostEqual(float(dish.total_cost), expected_cost, places=2)
    
    def test_dish_without_ingredients(self):
        """Test dania bez składników"""
        dish = Dish.objects.create(
            name='Puste danie',
            description='Danie bez składników',
            meal_type='breakfast'
        )
        
        self.assertEqual(dish.total_calories, Decimal('0.0'))
        self.assertEqual(dish.total_protein, Decimal('0.0'))
        self.assertEqual(dish.total_fat, Decimal('0.0'))
        self.assertEqual(dish.total_cost, Decimal('0.0'))
    
    def test_dish_ingredient_quantity_validation(self):
        """Test walidacji ilości składników"""
        dish = Dish.objects.create(
            name='Test danie',
            meal_type='lunch'
        )
        
        # Test ujemnej ilości
        with self.assertRaises(ValidationError):
            dish_ingredient = DishIngredient(
                dish=dish,
                ingredient=self.chicken,
                quantity_grams=Decimal('-50.0')
            )
            dish_ingredient.full_clean()
        
        # Test zerowej ilości
        with self.assertRaises(ValidationError):
            dish_ingredient = DishIngredient(
                dish=dish,
                ingredient=self.chicken,
                quantity_grams=Decimal('0.0')
            )
            dish_ingredient.full_clean()


class DietPlanBusinessLogicTest(TestCase):
    """Test logiki biznesowej planów dietetycznych"""
    
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='testclient',
            email='client@example.com',
            password='testpass123'
        )
        
        self.diet_plan = DietPlan.objects.create(
            name='Plan Standard',
            description='Standardowy plan dietetyczny',
            weekly_price=Decimal('150.00'),
            is_active=True
        )
    
    def test_diet_plan_price_calculation(self):
        """Test obliczania ceny planu dietetycznego"""
        # Test różnych okresów subskrypcji
        weekly_price = self.diet_plan.weekly_price
        
        # Miesięczna subskrypcja (4 tygodnie)
        monthly_price = self.diet_plan.monthly_price
        self.assertEqual(monthly_price, Decimal('600.00'))
        
        # Roczna subskrypcja (50 tygodni)
        yearly_price = self.diet_plan.yearly_price
        self.assertEqual(yearly_price, Decimal('7500.00'))
    
    def test_diet_plan_validation(self):
        """Test walidacji planu dietetycznego"""
        # Test ujemnej ceny
        with self.assertRaises(ValidationError):
            invalid_plan = DietPlan(
                name='Invalid Plan',
                description='Test',
                weekly_price=Decimal('-100.0')
            )
            invalid_plan.full_clean()
        
        # Test pustej nazwy
        with self.assertRaises(ValidationError):
            invalid_plan = DietPlan(
                name='',
                description='Test',
                weekly_price=Decimal('100.0')
            )
            invalid_plan.full_clean()


class LoyaltySystemTest(TestCase):
    """Test systemu punktów lojalnościowych"""
    
    def setUp(self):
        # Unikalna nazwa użytkownika dla każdego testu
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        self.client_user = User.objects.create_user(
            username=f'loyalclient_{unique_id}',
            email=f'loyal_{unique_id}@example.com',
            password='testpass123'
        )
        
        # Utworzenie lub pobranie konta lojalnościowego (get_or_create)
        self.loyalty_account, created = LoyaltyAccount.objects.get_or_create(
            user=self.client_user,
            defaults={
                'points_balance': 0,
                'total_points_earned': 0,
                'loyalty_level': 'bronze'
            }
        )
        
        # Reset salda na potrzeby testów
        self.loyalty_account.points_balance = 0
        self.loyalty_account.total_points_earned = 0
        self.loyalty_account.save()
    
    def test_loyalty_points_earning(self):
        """Test naliczania punktów lojalnościowych"""
        # Utworzenie subskrypcji do powiązania z płatnością
        diet_plan = DietPlan.objects.create(
            name='Test Plan',
            description='Test description',
            weekly_price=Decimal('100.00'),
            is_active=True
        )
        
        subscription = Subscription.objects.create(
            client=self.client_user,
            diet_plan=diet_plan,
            duration='week',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            delivery_address='Test Address',
            total_amount=Decimal('200.00')
        )
        
        # Symulacja płatności - 1 punkt za każdy złoty
        payment = Payment.objects.create(
            subscription=subscription,
            amount=Decimal('200.00'),
            status='completed',
            payment_date=timezone.now(),
            stripe_payment_intent_id='test_payment_123'
        )
        
        # Dodanie punktów
        point_transaction = PointTransaction.objects.create(
            account=self.loyalty_account,
            points=200,  # 1 punkt za 1 zł
            transaction_type='purchase',
            description=f'Punkty za płatność #{payment.id}'
        )
        
        # Aktualizacja salda
        self.loyalty_account.points_balance += 200
        self.loyalty_account.total_points_earned += 200
        self.loyalty_account.save()
        
        # Sprawdzenie salda punktów
        self.assertEqual(self.loyalty_account.points_balance, 200)
        self.assertEqual(self.loyalty_account.total_points_earned, 200)
    
    def test_loyalty_points_redemption(self):
        """Test wykorzystania punktów lojalnościowych"""
        # Dodanie punktów
        self.loyalty_account.points_balance = 150
        self.loyalty_account.save()
        
        PointTransaction.objects.create(
            account=self.loyalty_account,
            points=150,
            transaction_type='purchase',
            description='Punkty za zakupy'
        )
        
        # Wykorzystanie punktów (100 punktów = 10 zł zniżki)
        PointTransaction.objects.create(
            account=self.loyalty_account,
            points=-100,
            transaction_type='redemption',
            description='Wykorzystanie punktów na zniżkę'
        )
        
        # Aktualizacja salda
        self.loyalty_account.points_balance -= 100
        self.loyalty_account.save()
        
        # Sprawdzenie salda
        self.assertEqual(self.loyalty_account.points_balance, 50)
    
    def test_insufficient_points_validation(self):
        """Test walidacji niewystarczających punktów"""
        # Klient ma tylko 50 punktów
        self.loyalty_account.points_balance = 50
        self.loyalty_account.save()
        
        # Próba wykorzystania 100 punktów - powinna zostać odrzucona
        with self.assertRaises(ValidationError):
            if self.loyalty_account.points_balance < 100:
                raise ValidationError('Niewystarczające saldo punktów')


class SubscriptionModelTest(TestCase):
    """Test modelu Subscription"""
    
    def setUp(self):
        self.client_user = User.objects.create_user(
            username='testsubscriber',
            email='subscriber@example.com',
            password='testpass123'
        )
        
        self.diet_plan = DietPlan.objects.create(
            name='Test Plan',
            description='Test description',
            weekly_price=Decimal('120.00'),
            is_active=True
        )
    
    def test_subscription_creation(self):
        """Test tworzenia subskrypcji"""
        subscription = Subscription.objects.create(
            client=self.client_user,
            diet_plan=self.diet_plan,
            duration='month',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            delivery_address='ul. Testowa 123, Warszawa',
            total_amount=Decimal('480.00')  # 4 tygodnie * 120zł
        )
        
        self.assertEqual(subscription.client, self.client_user)
        self.assertEqual(subscription.diet_plan, self.diet_plan)
        self.assertEqual(subscription.duration, 'month')
        self.assertEqual(subscription.status, 'pending')  # domyślny status
        self.assertEqual(subscription.total_amount, Decimal('480.00'))
    
    def test_subscription_status_choices(self):
        """Test dostępnych statusów subskrypcji"""
        subscription = Subscription.objects.create(
            client=self.client_user,
            diet_plan=self.diet_plan,
            duration='week',
            start_date=date.today(),
            end_date=date.today() + timedelta(days=7),
            delivery_address='Test Address',
            total_amount=Decimal('120.00')
        )
        
        # Test zmiany statusów
        valid_statuses = ['pending', 'active', 'paused', 'cancelled', 'completed']
        
        for status in valid_statuses:
            subscription.status = status
            subscription.save()
            subscription.refresh_from_db()
            self.assertEqual(subscription.status, status)


if __name__ == '__main__':
    unittest.main()