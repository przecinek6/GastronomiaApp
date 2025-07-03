import json
from decimal import Decimal
from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import date, timedelta
from unittest.mock import patch, Mock

from frontend.models import (
    Ingredient, Dish, DishIngredient, DietPlan, 
    Subscription, Payment, LoyaltyAccount, PointTransaction, UserProfile
)


class APIEndpointsIntegrationTest(TestCase):
    """Test integracyjny API endpoints"""
    
    def setUp(self):
        self.client = Client()
        
        # Unikalne nazwy użytkowników
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        # Tworzenie użytkowników
        self.manager_user = User.objects.create_user(
            username=f'manager_{unique_id}',
            email=f'manager_{unique_id}@example.com',
            password='testpass123',
            is_staff=True
        )
        
        # WYCZYŚĆ istniejące profile i utwórz nowe
        UserProfile.objects.filter(user=self.manager_user).delete()
        UserProfile.objects.create(
            user=self.manager_user,
            role='manager'
        )
        
        self.client_user = User.objects.create_user(
            username=f'client_{unique_id}',
            email=f'client_{unique_id}@example.com',
            password='testpass123'
        )
        
        # WYCZYŚĆ istniejące profile i utwórz nowe
        UserProfile.objects.filter(user=self.client_user).delete()
        UserProfile.objects.create(
            user=self.client_user,
            role='client'
        )
        
        # Składniki testowe
        self.ingredient_chicken = Ingredient.objects.create(
            name='Kurczak pierś',
            calories_per_100g=Decimal('165.0'),
            protein_per_100g=Decimal('31.0'),
            fat_per_100g=Decimal('3.6'),
            price_per_100g=Decimal('2.50')
        )
        
        self.ingredient_rice = Ingredient.objects.create(
            name='Ryż basmati',
            calories_per_100g=Decimal('130.0'),
            protein_per_100g=Decimal('2.7'),
            fat_per_100g=Decimal('0.3'),
            price_per_100g=Decimal('1.20')
        )
        
        # Danie testowe
        self.dish = Dish.objects.create(
            name='Kurczak z ryżem',
            description='Klasyczne danie obiadowe',
            meal_type='lunch',
            allergens='gluten'
        )
        
        DishIngredient.objects.create(
            dish=self.dish,
            ingredient=self.ingredient_chicken,
            quantity_grams=Decimal('200.0')
        )
        
        DishIngredient.objects.create(
            dish=self.dish,
            ingredient=self.ingredient_rice,
            quantity_grams=Decimal('150.0')
        )
    
    def test_ingredient_data_api_authenticated_manager(self):
        """Test API pobierania danych składnika - autoryzowany manager"""
        self.client.force_login(self.manager_user)
        
        url = reverse('ingredient_data_api', kwargs={'ingredient_id': self.ingredient_chicken.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(data['name'], 'Kurczak pierś')
        self.assertEqual(data['calories_per_100g'], 165.0)
        self.assertEqual(data['protein_per_100g'], 31.0)
        self.assertEqual(data['fat_per_100g'], 3.6)
        self.assertEqual(data['price_per_100g'], 2.5)
    
    def test_ingredient_data_api_unauthorized_client(self):
        """Test API składnika - nieautoryzowany klient"""
        self.client.force_login(self.client_user)
        
        url = reverse('ingredient_data_api', kwargs={'ingredient_id': self.ingredient_chicken.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Brak uprawnień')
    
    def test_ingredient_data_api_not_found(self):
        """Test API składnika - nieistniejący składnik"""
        self.client.force_login(self.manager_user)
        
        url = reverse('ingredient_data_api', kwargs={'ingredient_id': 99999})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
        data = json.loads(response.content)
        self.assertEqual(data['error'], 'Składnik nie znaleziony')
    
    def test_ingredient_data_api_soft_deleted(self):
        """Test API składnika - soft deleted składnik"""
        self.client.force_login(self.manager_user)
        
        # Oznaczenie składnika jako usuniętego
        self.ingredient_chicken.is_deleted = True
        self.ingredient_chicken.save()
        
        url = reverse('ingredient_data_api', kwargs={'ingredient_id': self.ingredient_chicken.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 404)
    
    def test_ingredients_list_api_filtering(self):
        """Test API listy składników z filtrowaniem"""
        self.client.force_login(self.manager_user)
        
        # Dodanie usuniętego składnika
        deleted_ingredient = Ingredient.objects.create(
            name='Usunięty składnik',
            calories_per_100g=Decimal('100.0'),
            protein_per_100g=Decimal('10.0'),
            fat_per_100g=Decimal('5.0'),
            price_per_100g=Decimal('1.0'),
            is_deleted=True
        )
        
        url = reverse('ingredients_list_api')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        # Sprawdzenie czy usunięty składnik nie jest na liście
        ingredient_names = [ing['name'] for ing in data['ingredients']]
        self.assertIn('Kurczak pierś', ingredient_names)
        self.assertIn('Ryż basmati', ingredient_names)
        self.assertNotIn('Usunięty składnik', ingredient_names)
    

class SubscriptionWorkflowIntegrationTest(TestCase):
    """Test przepływów danych w systemie subskrypcji"""
    
    def setUp(self):
        self.client = Client()
        
        # Unikalne nazwy użytkowników
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        self.client_user = User.objects.create_user(
            username=f'subscriber_{unique_id}',
            email=f'subscriber_{unique_id}@example.com',
            password='testpass123'
        )
        
        # WYCZYŚĆ i utwórz profil klienta
        UserProfile.objects.filter(user=self.client_user).delete()
        UserProfile.objects.create(
            user=self.client_user,
            role='client'
        )
        
        self.diet_plan = DietPlan.objects.create(
            name='Plan Premium',
            description='Premium plan dietetyczny',
            weekly_price=Decimal('200.00'),
            is_active=True
        )
    
    def test_subscription_creation_workflow(self):
        """Test kompletnego procesu tworzenia subskrypcji"""
        self.client.login(username='subscriber', password='testpass123')
        
        # Krok 1: Utworzenie subskrypcji
        subscription_data = {
            'diet_plan': self.diet_plan.id,
            'subscription_type': 'monthly',
            'start_date': date.today() + timedelta(days=1),
            'delivery_address': 'ul. Testowa 123, 00-001 Warszawa',
            'delivery_instructions': 'Pozostawić pod drzwiami'
        }
        
        subscription = Subscription.objects.create(
            client=self.client_user,
            diet_plan=self.diet_plan,
            duration='month',
            start_date=subscription_data['start_date'],
            end_date=subscription_data['start_date'] + timedelta(days=30),
            delivery_address=subscription_data['delivery_address'],
            delivery_notes=subscription_data['delivery_instructions'],
            total_amount=Decimal('800.00')  # 4 tygodnie * 200zł
        )
        
        # Weryfikacja utworzenia subskrypcji
        self.assertEqual(subscription.status, 'pending')  # domyślnie pending
        self.assertEqual(subscription.total_amount, Decimal('800.00'))
        
        # Krok 2: Symulacja płatności
        payment = Payment.objects.create(
            subscription=subscription,
            amount=subscription.total_amount,
            status='completed',
            payment_date=timezone.now(),
            stripe_payment_intent_id=f'test_payment_{subscription.id}'
        )
        
        # Krok 3: Naliczenie punktów lojalnościowych
        loyalty_account, created = LoyaltyAccount.objects.get_or_create(
            user=self.client_user,
            defaults={
                'points_balance': int(payment.amount),
                'total_points_earned': int(payment.amount),
                'loyalty_level': 'bronze'
            }
        )
        
        # Jeśli konto już istniało, zaktualizuj saldo
        if not created:
            loyalty_account.points_balance += int(payment.amount)
            loyalty_account.total_points_earned += int(payment.amount)
            loyalty_account.save()
        
        PointTransaction.objects.create(
            account=loyalty_account,
            points=int(payment.amount),  # 1 punkt za 1 zł
            transaction_type='purchase',
            description=f'Punkty za subskrypcję #{subscription.id}'
        )
        
        # Weryfikacja całego procesu
        self.assertEqual(payment.status, 'completed')
        self.assertEqual(loyalty_account.points_balance, 800)
        
        # Sprawdzenie salda punktów klienta
        self.assertEqual(loyalty_account.points_balance, 800)


class ErrorHandlingIntegrationTest(TestCase):
    """Test obsługi błędów i edge cases"""
    
    def setUp(self):
        self.client = Client()
        
        # Unikalne nazwy użytkowników
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        self.manager_user = User.objects.create_user(
            username=f'manager_{unique_id}',
            email=f'manager_{unique_id}@example.com',
            password='testpass123',
            is_staff=True
        )
        
        # WYCZYŚĆ i utwórz profil managera
        UserProfile.objects.filter(user=self.manager_user).delete()
        UserProfile.objects.create(
            user=self.manager_user,
            role='manager'
        )
    
    def test_api_unauthenticated_access(self):
        """Test dostępu do API bez uwierzytelnienia"""
        ingredient = Ingredient.objects.create(
            name='Test Ingredient',
            calories_per_100g=Decimal('100.0'),
            protein_per_100g=Decimal('10.0'),
            fat_per_100g=Decimal('5.0'),
            price_per_100g=Decimal('1.0')
        )
        
        url = reverse('ingredient_data_api', kwargs={'ingredient_id': ingredient.id})
        response = self.client.get(url)
        
        # Powinien przekierować do strony logowania lub zwrócić 401/403
        self.assertIn(response.status_code, [302, 401, 403])
    
    def test_api_malformed_requests(self):
        """Test obsługi niepoprawnych żądań API"""
        self.client.force_login(self.manager_user)
        
        # Test z niepoprawnym ID (string zamiast int)
        response = self.client.get('/api/ingredient/invalid_id/')
        self.assertEqual(response.status_code, 404)
        
        # Test z ID = 0
        response = self.client.get('/api/ingredient/0/')
        self.assertEqual(response.status_code, 404)
        
        # Test z ujemnym ID
        response = self.client.get('/api/ingredient/-1/')
        self.assertEqual(response.status_code, 404)
    
    def test_edge_case_zero_quantity_ingredients(self):
        """Test edge case - składniki z zerowymi ilościami"""
        dish = Dish.objects.create(
            name='Edge Case Dish',
            meal_type='breakfast'
        )
        
        ingredient = Ingredient.objects.create(
            name='Zero Ingredient',
            calories_per_100g=Decimal('100.0'),
            protein_per_100g=Decimal('10.0'),
            fat_per_100g=Decimal('5.0'),
            price_per_100g=Decimal('1.0')
        )
        
        # Sprawdzenie czy API radzi sobie z daniem bez składników
        url = reverse('dish_detail_api', kwargs={'dish_id': dish.id})
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        data = json.loads(response.content)
        
        self.assertEqual(data['total_calories'], 0.0)
        self.assertEqual(data['total_protein'], 0.0)
        self.assertEqual(data['total_fat'], 0.0)
        self.assertEqual(data['total_cost'], 0.0)
        self.assertEqual(len(data['ingredients']), 0)
    
    def test_subscription_edge_cases(self):
        """Test edge cases w subskrypcjach"""
        # Unikalna nazwa użytkownika
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        
        client_user = User.objects.create_user(
            username=f'edge_client_{unique_id}',
            email=f'edge_{unique_id}@example.com',
            password='testpass123'
        )
        
        UserProfile.objects.get_or_create(
            user=client_user,
            defaults={'role': 'client'}
        )
        
        diet_plan = DietPlan.objects.create(
            name='Edge Plan',
            description='Plan do testów edge cases',
            weekly_price=Decimal('100.00'),
            is_active=True
        )
        
        # Test subskrypcji z datą rozpoczęcia w przeszłości
        past_date = date.today() - timedelta(days=5)
        subscription = Subscription.objects.create(
            client=client_user,
            diet_plan=diet_plan,
            duration='week',
            start_date=past_date,
            end_date=past_date + timedelta(days=7),
            delivery_address='Test Address',
            total_amount=Decimal('100.00')
        )
        
        # Sprawdzenie czy subskrypcja została utworzona mimo daty w przeszłości
        self.assertEqual(subscription.status, 'pending')  # domyślnie pending
        
        # Test bardzo krótkiej subskrypcji (1 dzień)
        tomorrow = date.today() + timedelta(days=1)
        short_subscription = Subscription.objects.create(
            client=client_user,
            diet_plan=diet_plan,
            duration='week',
            start_date=tomorrow,
            end_date=tomorrow + timedelta(days=1),
            delivery_address='Test Address',
            total_amount=Decimal('100.00')
        )
        
        self.assertEqual(short_subscription.status, 'pending')