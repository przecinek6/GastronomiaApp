from django.db import models
from django.contrib.auth.models import User
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
import uuid

# ==========================================
# 1. ROZSZERZENIE USER
# ==========================================

# Zastąp istniejącą klasę UserProfile w frontend/models.py
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

# ==========================================
# 2. SKŁADNIKI
# ==========================================

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

# ==========================================
# 3. DANIA
# ==========================================

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

# ==========================================
# 4. PLANY DIETETYCZNE
# ==========================================

class DietPlan(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
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

# ==========================================
# 5. SUBSKRYPCJE I ZAMÓWIENIA
# ==========================================

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
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(User, on_delete=models.CASCADE)
    diet_plan = models.ForeignKey(DietPlan, on_delete=models.CASCADE)
    duration = models.CharField(max_length=20, choices=DURATION_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    start_date = models.DateField()
    end_date = models.DateField()
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    
    # Stripe integration
    stripe_subscription_id = models.CharField(max_length=200, blank=True)
    stripe_customer_id = models.CharField(max_length=200, blank=True)
    
    # Delivery details
    delivery_address = models.TextField()
    delivery_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Tracking changes
    diet_changes_count = models.IntegerField(default=0)
    
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
    
    def can_change_diet(self):
        """Sprawdź czy można zmienić dietę (max 2 razy w miesiącu)"""
        return self.diet_changes_count < 2
    
    @property
    def is_active(self):
        return self.status == 'active' and self.start_date <= timezone.now().date() <= self.end_date

class DietChange(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Oczekująca'),
        ('confirmed', 'Potwierdzona'),
        ('completed', 'Wykonana'),
        ('cancelled', 'Anulowana'),
    ]
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    old_plan = models.ForeignKey(DietPlan, on_delete=models.CASCADE, related_name='old_changes')
    new_plan = models.ForeignKey(DietPlan, on_delete=models.CASCADE, related_name='new_changes')
    change_date = models.DateField()
    reason = models.CharField(max_length=200, blank=True)
    price_adjustment = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.subscription.client.username} - {self.old_plan.name} → {self.new_plan.name}"

# ==========================================
# 6. PŁATNOŚCI
# ==========================================

class Payment(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Oczekująca'),
        ('completed', 'Zakończona'),
        ('failed', 'Nieudana'),
        ('refunded', 'Zwrócona'),
    ]
    
    subscription = models.ForeignKey(Subscription, on_delete=models.CASCADE)
    stripe_payment_intent_id = models.CharField(max_length=200, unique=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    payment_date = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Płatność {self.amount} zł - {self.subscription.client.username}"

# ==========================================
# 7. SYSTEM LOJALNOŚCIOWY
# ==========================================

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

# ==========================================
# 8. ZARZĄDZANIE ZAKUPAMI I DOSTAWAMI
# ==========================================

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

# ==========================================
# 9. DODATKOWE MODELE POMOCNICZE
# ==========================================

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