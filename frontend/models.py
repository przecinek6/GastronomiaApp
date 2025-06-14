from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('manager', 'Menadżer'),
        ('client', 'Klient'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='client')
    phone = models.CharField(max_length=15, blank=True)
    
    # Szczegółowe pola adresu dostawy
    delivery_city = models.CharField(max_length=100, blank=True)
    delivery_postal_code = models.CharField(max_length=10, blank=True)
    delivery_street = models.CharField(max_length=200, blank=True)
    delivery_building_number = models.CharField(max_length=20, blank=True)
    delivery_apartment_number = models.CharField(max_length=20, blank=True)
    delivery_notes = models.TextField(blank=True)
    
    date_of_birth = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Ustawienia powiadomień
    newsletter = models.BooleanField(default=True)
    subscription_reminders = models.BooleanField(default=True)
    delivery_notifications = models.BooleanField(default=True)
    diet_change_confirmations = models.BooleanField(default=True)
    promotional_offers = models.BooleanField(default=False)
    
    @property
    def full_delivery_address(self):
        """Zwraca pełny adres dostawy jako string"""
        parts = []
        if self.delivery_street and self.delivery_building_number:
            apartment = f"/{self.delivery_apartment_number}" if self.delivery_apartment_number else ""
            parts.append(f"{self.delivery_street} {self.delivery_building_number}{apartment}")
        if self.delivery_postal_code and self.delivery_city:
            parts.append(f"{self.delivery_postal_code} {self.delivery_city}")
        return ", ".join(parts) if parts else "Brak adresu dostawy"


class Ingredient(models.Model):
    name = models.CharField(max_length=100, unique=True)
    calories_per_100g = models.DecimalField(
        max_digits=6, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    protein_per_100g = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    fat_per_100g = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    price_per_100g = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  # Soft delete
    
    class Meta:
        ordering = ['name']
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['is_deleted']),
        ]
    
    def __str__(self):
        return self.name
    
    def delete(self, *args, **kwargs):
        self.is_deleted = True
        self.save()

class Dish(models.Model):
    MEAL_TYPE_CHOICES = [
        ('breakfast', 'Śniadanie'),
        ('lunch', 'Obiad'),
        ('dinner', 'Kolacja'),
        ('any', 'Dowolny posiłek'),
    ]
    
    name = models.CharField(max_length=150)
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES, default='any')
    allergens = models.TextField(blank=True, help_text="Lista alergenów oddzielona przecinkami")
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='dishes/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_deleted = models.BooleanField(default=False)  # Soft delete
    
    class Meta:
        ordering = ['name']
        verbose_name_plural = "Dishes"
        indexes = [
            models.Index(fields=['meal_type', 'is_deleted']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def total_cost(self):
        """Oblicz całkowity koszt dania na podstawie składników"""
        total = Decimal('0.00')
        for dish_ingredient in self.dishingredient_set.all():
            ingredient_cost = (dish_ingredient.ingredient.price_per_100g * dish_ingredient.quantity_grams) / 100
            total += ingredient_cost
        return total
    
    @property
    def total_calories(self):
        """Oblicz całkowitą liczbę kalorii"""
        total = Decimal('0.00')
        for dish_ingredient in self.dishingredient_set.all():
            calories = (dish_ingredient.ingredient.calories_per_100g * dish_ingredient.quantity_grams) / 100
            total += calories
        return total
    
    @property
    def total_protein(self):
        """Oblicz całkowitą ilość białka"""
        total = Decimal('0.00')
        for dish_ingredient in self.dishingredient_set.all():
            protein = (dish_ingredient.ingredient.protein_per_100g * dish_ingredient.quantity_grams) / 100
            total += protein
        return total
    
    @property
    def total_fat(self):
        """Oblicz całkowitą ilość tłuszczów"""
        total = Decimal('0.00')
        for dish_ingredient in self.dishingredient_set.all():
            fat = (dish_ingredient.ingredient.fat_per_100g * dish_ingredient.quantity_grams) / 100
            total += fat
        return total
    
    def get_allergens_list(self):
        """Zwraca listę alergenów jako listę stringów"""
        if self.allergens:
            return [allergen.strip() for allergen in self.allergens.split(',') if allergen.strip()]
        return []
    
    def get_ingredient_count(self):
        """Zwraca liczbę składników w daniu"""
        return self.dishingredient_set.count()
    
    def delete(self, *args, **kwargs):
        """Soft delete"""
        self.is_deleted = True
        self.save()

class DishIngredient(models.Model):
    """Relacja many-to-many między daniami a składnikami z ilościami"""
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    quantity_grams = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(0.01)]
    )
    
    class Meta:
        unique_together = ['dish', 'ingredient']
    
    def __str__(self):
        return f"{self.dish.name} - {self.ingredient.name} ({self.quantity_grams}g)"



class DietPlan(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    image = models.ImageField(upload_to='diet_plans/', blank=True, null=True)
    weekly_price = models.DecimalField(
        max_digits=8, 
        decimal_places=2,
        validators=[MinValueValidator(0)]
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    @property
    def monthly_price(self):
        return self.weekly_price * 4
    
    @property
    def yearly_price(self):
        return self.weekly_price * 50  # 50 tygodni (2 tygodnie urlopu)

class MealPlan(models.Model):
    DAYS_OF_WEEK = [
        (1, 'Poniedziałek'),
        (2, 'Wtorek'),
        (3, 'Środa'),
        (4, 'Czwartek'),
        (5, 'Piątek'),
        (6, 'Sobota'),
        (7, 'Niedziela'),
    ]
    
    MEAL_TYPES = [
        ('breakfast', 'Śniadanie'),
        ('lunch', 'Obiad'),
        ('dinner', 'Kolacja'),
    ]
    
    diet_plan = models.ForeignKey(DietPlan, on_delete=models.CASCADE)
    day_of_week = models.IntegerField(choices=DAYS_OF_WEEK)
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES)
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ['diet_plan', 'day_of_week', 'meal_type']
    
    def __str__(self):
        return f"{self.diet_plan.name} - {self.get_day_of_week_display()} - {self.get_meal_type_display()}"


class Subscription(models.Model):
    DURATION_CHOICES = [
        ('week', '1 tydzień'),
        ('month', '1 miesiąc'),
        ('year', '1 rok'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Oczekująca'),
        ('active', 'Aktywna'),
        ('paused', 'Wstrzymana'),
        ('cancelled', 'Anulowana'),
        ('completed', 'Zakończona'),
    ]
    
    # Podstawowe informacje
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(User, on_delete=models.CASCADE, related_name='subscriptions')
    diet_plan = models.ForeignKey('DietPlan', on_delete=models.CASCADE)
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Daty
    start_date = models.DateField()
    end_date = models.DateField()
    
    # Finanse - WSZYSTKO W DECIMAL!
    total_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    # Symulacja Stripe
    stripe_subscription_id = models.CharField(
        max_length=200, 
        blank=True,
        help_text="W symulacji: SIM_SUB_{UUID}"
    )
    stripe_customer_id = models.CharField(
        max_length=200, 
        blank=True,
        help_text="W symulacji: SIM_CUS_{user_id}"
    )
    
    # Delivery details
    delivery_address = models.TextField()
    delivery_notes = models.TextField(blank=True)
    
    # Metadane
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tracking changes
    diet_changes_count = models.IntegerField(default=0)
    
    # Pauzy
    pause_start_date = models.DateField(null=True, blank=True)
    pause_end_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['stripe_subscription_id']),
        ]
    
    def __str__(self):
        return f"{self.client.username} - {self.diet_plan.name} ({self.duration})"
    
    def save(self, *args, **kwargs):
        # Automatyczne generowanie symulowanych ID Stripe
        if not self.stripe_subscription_id and self.status != 'pending':
            self.stripe_subscription_id = f'SIM_SUB_{self.id}'
        if not self.stripe_customer_id and self.client_id:
            self.stripe_customer_id = f'SIM_CUS_{self.client_id}'
        super().save(*args, **kwargs)
    
    def can_change_diet(self):
        """Sprawdź czy można zmienić dietę (max 2 razy w miesiącu)"""
        return self.diet_changes_count < 2
    
    @property
    def is_active(self):
        """Sprawdź czy subskrypcja jest aktywna"""
        today = timezone.now().date()
        if self.status != 'active':
            return False
        if self.pause_start_date and self.pause_end_date:
            if self.pause_start_date <= today <= self.pause_end_date:
                return False
        return self.start_date <= today <= self.end_date
    
    @property
    def days_remaining(self):
        """Liczba pozostałych dni subskrypcji"""
        if self.end_date < timezone.now().date():
            return 0
        return (self.end_date - timezone.now().date()).days
    
    @property
    def daily_rate(self):
        """Dzienna stawka subskrypcji"""
        total_days = (self.end_date - self.start_date).days
        if total_days == 0:
            return Decimal('0.00')
        return self.total_amount / Decimal(str(total_days))
    
    def calculate_refund(self, refund_date=None):
        """Oblicz kwotę zwrotu"""
        if refund_date is None:
            refund_date = timezone.now().date()
        
        days_used = (refund_date - self.start_date).days
        total_days = (self.end_date - self.start_date).days
        days_remaining = max(0, total_days - days_used)
        
        return self.daily_rate * Decimal(str(days_remaining))


class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Oczekująca'),
        ('processing', 'Przetwarzana'),
        ('completed', 'Zakończona'),
        ('failed', 'Nieudana'),
        ('refunded', 'Zwrócona'),
        ('partial_refund', 'Częściowy zwrot'),
    ]
    
    PAYMENT_TYPE_CHOICES = [
        ('subscription', 'Opłata za subskrypcję'),
        ('adjustment', 'Dopłata za zmianę'),
        ('refund', 'Zwrot'),
        ('partial_refund', 'Częściowy zwrot'),
    ]
    
    REFUND_TYPE_CHOICES = [
        ('money', 'Pieniądze'),
        ('points', 'Punkty lojalnościowe'),
    ]
    
    # Relacje
    subscription = models.ForeignKey(
        Subscription, 
        on_delete=models.CASCADE,
        related_name='payments'
    )
    
    # Typ płatności
    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default='subscription'
    )
    
    # Symulacja Stripe
    stripe_payment_intent_id = models.CharField(
        max_length=200, 
        unique=True,
        help_text="W symulacji: SIM_PAY_{UUID}"
    )
    
    # Kwoty - DECIMAL dla dokładności finansowej
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        help_text="Ujemna wartość dla zwrotów"
    )
    
    # Status
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    
    # Typ zwrotu (jeśli dotyczy)
    refund_type = models.CharField(
        max_length=20,
        choices=REFUND_TYPE_CHOICES,
        null=True,
        blank=True,
        help_text="Typ zwrotu - pieniądze lub punkty"
    )
    
    # Punkty lojalnościowe (jeśli zwrot w punktach)
    loyalty_points_refunded = models.IntegerField(
        default=0,
        help_text="Liczba zwróconych punktów lojalnościowych"
    )
    
    # Metadane
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Dodatkowe informacje
    description = models.TextField(blank=True)
    metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dodatkowe dane w formacie JSON"
    )
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['subscription', 'status']),
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['payment_date']),
            models.Index(fields=['payment_type']),
        ]
    
    def __str__(self):
        return f"Płatność {self.amount} zł - {self.subscription.client.username}"
    
    def save(self, *args, **kwargs):
        # Automatyczne generowanie symulowanych ID
        if not self.stripe_payment_intent_id:
            prefix = 'SIM_REFUND' if self.amount < 0 else 'SIM_PAY'
            self.stripe_payment_intent_id = f'{prefix}_{uuid.uuid4()}'
        
        # Ustaw datę płatności jeśli zakończona
        if self.status == 'completed' and not self.payment_date:
            self.payment_date = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def is_refund(self):
        """Sprawdź czy to zwrot"""
        return self.amount < 0 or self.payment_type in ['refund', 'partial_refund']
    
    def process_refund_as_points(self):
        """Przetworz zwrot jako punkty lojalnościowe"""
        if not self.is_refund:
            raise ValueError("To nie jest płatność typu zwrot")
        
        points = int(abs(self.amount))
        self.loyalty_points_refunded = points
        self.refund_type = 'points'
        self.status = 'completed'
        self.save()
        
        # Dodaj punkty do konta lojalnościowego
        from .models import LoyaltyAccount
        loyalty_account, created = LoyaltyAccount.objects.get_or_create(
            user=self.subscription.client,
            defaults={'points_balance': 0, 'total_points_earned': 0}
        )
        
        loyalty_account.add_points(
            points=points,
            transaction_type='adjustment',
            description=f'Zwrot za {self.description or "anulowaną subskrypcję"}',
            related_order=self.subscription
        )
        
        return points


class LoyaltyAccount(models.Model):
    LOYALTY_LEVELS = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
        ('platinum', 'Platinum'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    points_balance = models.IntegerField(default=0)
    total_points_earned = models.IntegerField(default=0)
    loyalty_level = models.CharField(max_length=20, choices=LOYALTY_LEVELS, default='bronze')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.points_balance} punktów ({self.loyalty_level})"
    
    def add_points(self, points, transaction_type, description, related_order=None):
        """Dodaj punkty do konta"""
        self.points_balance += points
        if points > 0:
            self.total_points_earned += points
        
        # Aktualizuj poziom lojalnościowy
        self.update_loyalty_level()
        self.save()
        
        # Zapisz transakcję
        PointTransaction.objects.create(
            account=self,
            points=points,
            transaction_type=transaction_type,
            description=description,
            related_order=related_order
        )
    
    def update_loyalty_level(self):
        """Aktualizuj poziom lojalnościowy na podstawie całkowitych punktów"""
        if self.total_points_earned >= 2000:
            self.loyalty_level = 'platinum'
        elif self.total_points_earned >= 1000:
            self.loyalty_level = 'gold'
        elif self.total_points_earned >= 500:
            self.loyalty_level = 'silver'
        else:
            self.loyalty_level = 'bronze'

class PointTransaction(models.Model):
    TRANSACTION_TYPES = [
        ('purchase', 'Zakup'),
        ('referral', 'Polecenie'),
        ('review', 'Opinia'),
        ('redemption', 'Wykorzystanie'),
        ('bonus', 'Bonus'),
        ('adjustment', 'Korekta'),
    ]
    
    account = models.ForeignKey(LoyaltyAccount, on_delete=models.CASCADE)
    points = models.IntegerField()  # + dla dodania, - dla wykorzystania
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPES)
    description = models.TextField()
    related_order = models.ForeignKey(Subscription, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.account.user.username} - {self.points} punktów ({self.transaction_type})"

class ReferralProgram(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Oczekujące'),
        ('completed', 'Zaliczone'),
        ('expired', 'Wygasłe'),
    ]
    
    referrer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referrals_made')
    referred = models.ForeignKey(User, on_delete=models.CASCADE, related_name='referred_by')
    referral_code = models.CharField(max_length=50, unique=True)
    reward_points = models.IntegerField(default=100)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.referrer.username} → {self.referred.username}"

class ShoppingList(models.Model):
    name = models.CharField(max_length=100)
    week_start_date = models.DateField()
    week_end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-week_start_date']
    
    def __str__(self):
        return f"Lista zakupów {self.week_start_date} - {self.week_end_date}"

class ShoppingListItem(models.Model):
    shopping_list = models.ForeignKey(ShoppingList, on_delete=models.CASCADE)
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE)
    required_quantity = models.DecimalField(max_digits=10, decimal_places=2)  # w gramach
    estimated_cost = models.DecimalField(max_digits=8, decimal_places=2)
    is_purchased = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ['shopping_list', 'ingredient']
    
    def __str__(self):
        return f"{self.ingredient.name} - {self.required_quantity}g"

class Delivery(models.Model):
    STATUS_CHOICES = [
        ('preparing', 'W przygotowaniu'),
        ('ready', 'Gotowe'),
        ('in_transit', 'W drodze'),
        ('delivered', 'Dostarczone'),
        ('failed', 'Nieudane'),
    ]
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    delivery_date = models.DateField()
    delivery_address = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='preparing')
    delivery_notes = models.TextField(blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['delivery_date', '-created_at']
    
    def __str__(self):
        return f"Dostawa {self.subscription.client.username} - {self.delivery_date}"


class ContactMessage(models.Model):
    name = models.CharField(max_length=100)
    email = models.EmailField()
    subject = models.CharField(max_length=200)
    message = models.TextField()
    is_resolved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.name} - {self.subject}"

class SystemSettings(models.Model):
    """Ustawienia systemowe dla aplikacji"""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField()
    description = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "System Settings"
    
    def __str__(self):
        return f"{self.key}: {self.value[:50]}"
    

class DietChange(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Oczekująca'),
        ('confirmed', 'Potwierdzona'),
        ('completed', 'Wykonana'),
        ('cancelled', 'Anulowana'),
    ]
    
    subscription = models.ForeignKey(
        Subscription, 
        on_delete=models.CASCADE,
        related_name='diet_changes'
    )
    old_plan = models.ForeignKey(
        'DietPlan', 
        on_delete=models.CASCADE, 
        related_name='old_changes'
    )
    new_plan = models.ForeignKey(
        'DietPlan', 
        on_delete=models.CASCADE, 
        related_name='new_changes'
    )
    
    change_date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    
    # Finansowe - używaj DECIMAL!
    price_adjustment = models.DecimalField(
        max_digits=8, 
        decimal_places=2, 
        default=Decimal('0.00'),
        help_text="Dopłata (+) lub zwrot (-)"
    )
    
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pending'
    )
    
    # Powiązana płatność (jeśli była dopłata/zwrot)
    related_payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='diet_changes'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.subscription.client.username} - {self.old_plan.name} → {self.new_plan.name}"
    
    def calculate_price_adjustment(self):
        """Oblicz dopłatę/zwrot za zmianę diety"""
        days_remaining = (self.subscription.end_date - self.change_date).days
        
        old_daily_rate = self.subscription.daily_rate
        
        # Oblicz nową stawkę dzienną
        if self.subscription.duration == 'week':
            new_total = self.new_plan.weekly_price
        elif self.subscription.duration == 'month':
            new_total = self.new_plan.monthly_price
        else:  # year
            new_total = self.new_plan.yearly_price
        
        total_days = (self.subscription.end_date - self.subscription.start_date).days
        new_daily_rate = new_total / Decimal(str(total_days))
        
        # Oblicz różnicę
        daily_diff = new_daily_rate - old_daily_rate
        self.price_adjustment = daily_diff * Decimal(str(days_remaining))
        
        return self.price_adjustment