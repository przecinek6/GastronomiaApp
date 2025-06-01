from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
from frontend.models import (
    UserProfile, Ingredient, Dish, DishIngredient, DietPlan, MealPlan,
    Subscription, DietChange, Payment, LoyaltyAccount, PointTransaction,
    ReferralProgram, ShoppingList, ShoppingListItem, Delivery,
    ContactMessage, SystemSettings
)

# ==========================================
# INLINE ADMINS
# ==========================================

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

class DishIngredientInline(admin.TabularInline):
    model = DishIngredient
    extra = 0
    autocomplete_fields = ['ingredient']

class MealPlanInline(admin.TabularInline):
    model = MealPlan
    extra = 0
    autocomplete_fields = ['dish']

class ShoppingListItemInline(admin.TabularInline):
    model = ShoppingListItem
    extra = 0
    readonly_fields = ['estimated_cost']
    autocomplete_fields = ['ingredient']

class PointTransactionInline(admin.TabularInline):
    model = PointTransaction
    extra = 0
    readonly_fields = ['created_at']

# ==========================================
# MAIN ADMIN CLASSES
# ==========================================

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role', 'is_staff', 'date_joined')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'userprofile__role')
    search_fields = ('username', 'first_name', 'last_name', 'email')
    
    def get_role(self, obj):
        try:
            return obj.userprofile.get_role_display()
        except UserProfile.DoesNotExist:
            return 'Brak profilu'
    get_role.short_description = 'Rola'

@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ('name', 'calories_per_100g', 'protein_per_100g', 'fat_per_100g', 'price_per_100g', 'created_at', 'is_deleted')
    list_filter = ('is_deleted', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('created_at', 'updated_at')
    list_editable = ('price_per_100g',)
    
    def get_queryset(self, request):
        # Pokaż również soft-deleted items w admin
        return Ingredient.objects.all()

@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'meal_type', 'get_total_cost', 'get_total_calories', 'created_at', 'is_deleted')
    list_filter = ('meal_type', 'is_deleted', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'get_total_cost', 'get_total_calories', 'get_total_protein', 'get_total_fat')
    inlines = [DishIngredientInline]
    filter_horizontal = []
    
    def get_total_cost(self, obj):
        return f"{obj.total_cost:.2f} zł"
    get_total_cost.short_description = 'Koszt całkowity'
    
    def get_total_calories(self, obj):
        return f"{obj.total_calories:.1f} kcal"
    get_total_calories.short_description = 'Kalorie'
    
    def get_total_protein(self, obj):
        return f"{obj.total_protein:.1f} g"
    get_total_protein.short_description = 'Białko'
    
    def get_total_fat(self, obj):
        return f"{obj.total_fat:.1f} g"
    get_total_fat.short_description = 'Tłuszcze'
    
    def get_queryset(self, request):
        return Dish.objects.all()

@admin.register(DietPlan)
class DietPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'weekly_price', 'get_monthly_price', 'get_yearly_price', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'get_monthly_price', 'get_yearly_price')
    inlines = [MealPlanInline]
    
    def get_monthly_price(self, obj):
        return f"{obj.monthly_price:.2f} zł"
    get_monthly_price.short_description = 'Cena miesięczna'
    
    def get_yearly_price(self, obj):
        return f"{obj.yearly_price:.2f} zł"
    get_yearly_price.short_description = 'Cena roczna'

@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('get_client_name', 'diet_plan', 'duration', 'status', 'start_date', 'end_date', 'total_amount', 'is_active_status')
    list_filter = ('status', 'duration', 'start_date', 'diet_plan')
    search_fields = ('client__username', 'client__email', 'diet_plan__name')
    readonly_fields = ('id', 'created_at', 'updated_at', 'is_active_status')
    date_hierarchy = 'start_date'
    
    def get_client_name(self, obj):
        return f"{obj.client.first_name} {obj.client.last_name}" or obj.client.username
    get_client_name.short_description = 'Klient'
    
    def is_active_status(self, obj):
        return obj.is_active
    is_active_status.boolean = True
    is_active_status.short_description = 'Aktywna'

@admin.register(DietChange)
class DietChangeAdmin(admin.ModelAdmin):
    list_display = ('get_client_name', 'old_plan', 'new_plan', 'change_date', 'status', 'price_adjustment', 'created_at')
    list_filter = ('status', 'change_date', 'created_at')
    search_fields = ('subscription__client__username', 'old_plan__name', 'new_plan__name')
    readonly_fields = ('created_at',)
    
    def get_client_name(self, obj):
        return obj.subscription.client.username
    get_client_name.short_description = 'Klient'

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ('get_client_name', 'amount', 'status', 'payment_date', 'stripe_payment_intent_id', 'created_at')
    list_filter = ('status', 'payment_date', 'created_at')
    search_fields = ('subscription__client__username', 'stripe_payment_intent_id')
    readonly_fields = ('created_at',)
    
    def get_client_name(self, obj):
        return obj.subscription.client.username
    get_client_name.short_description = 'Klient'

@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = ('get_user_name', 'points_balance', 'total_points_earned', 'loyalty_level', 'created_at')
    list_filter = ('loyalty_level', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at', 'total_points_earned')
    inlines = [PointTransactionInline]
    
    def get_user_name(self, obj):
        return obj.user.username
    get_user_name.short_description = 'Użytkownik'

@admin.register(PointTransaction)
class PointTransactionAdmin(admin.ModelAdmin):
    list_display = ('get_user_name', 'points', 'transaction_type', 'description', 'created_at')
    list_filter = ('transaction_type', 'created_at')
    search_fields = ('account__user__username', 'description')
    readonly_fields = ('created_at',)
    
    def get_user_name(self, obj):
        return obj.account.user.username
    get_user_name.short_description = 'Użytkownik'

@admin.register(ReferralProgram)
class ReferralProgramAdmin(admin.ModelAdmin):
    list_display = ('get_referrer_name', 'get_referred_name', 'referral_code', 'reward_points', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('referrer__username', 'referred__username', 'referral_code')
    readonly_fields = ('created_at', 'completed_at')
    
    def get_referrer_name(self, obj):
        return obj.referrer.username
    get_referrer_name.short_description = 'Polecający'
    
    def get_referred_name(self, obj):
        return obj.referred.username
    get_referred_name.short_description = 'Polecony'

@admin.register(ShoppingList)
class ShoppingListAdmin(admin.ModelAdmin):
    list_display = ('name', 'week_start_date', 'week_end_date', 'is_completed', 'created_at')
    list_filter = ('is_completed', 'week_start_date')
    search_fields = ('name',)
    readonly_fields = ('created_at',)
    inlines = [ShoppingListItemInline]
    date_hierarchy = 'week_start_date'

@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = ('get_client_name', 'delivery_date', 'status', 'delivery_address_short', 'delivered_at', 'created_at')
    list_filter = ('status', 'delivery_date', 'created_at')
    search_fields = ('subscription__client__username', 'delivery_address')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'delivery_date'
    
    def get_client_name(self, obj):
        return obj.subscription.client.username
    get_client_name.short_description = 'Klient'
    
    def delivery_address_short(self, obj):
        return obj.delivery_address[:50] + '...' if len(obj.delivery_address) > 50 else obj.delivery_address
    delivery_address_short.short_description = 'Adres dostawy'

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ('name', 'email', 'subject', 'is_resolved', 'created_at')
    list_filter = ('is_resolved', 'created_at')
    search_fields = ('name', 'email', 'subject')
    readonly_fields = ('created_at',)
    
    def mark_as_resolved(self, request, queryset):
        updated = queryset.update(is_resolved=True)
        self.message_user(request, f'{updated} wiadomości zostały oznaczone jako rozwiązane.')
    mark_as_resolved.short_description = 'Oznacz jako rozwiązane'
    
    actions = ['mark_as_resolved']

@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('key', 'value_short', 'description_short', 'updated_at')
    search_fields = ('key', 'value', 'description')
    readonly_fields = ('updated_at',)
    
    def value_short(self, obj):
        return obj.value[:50] + '...' if len(obj.value) > 50 else obj.value
    value_short.short_description = 'Wartość'
    
    def description_short(self, obj):
        return obj.description[:100] + '...' if len(obj.description) > 100 else obj.description
    description_short.short_description = 'Opis'

# ==========================================
# UNREGISTER AND REGISTER
# ==========================================

# Wyrejestruj domyślny UserAdmin i zarejestruj customowy
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# ==========================================
# ADMIN SITE CUSTOMIZATION
# ==========================================

admin.site.site_header = "GastronomiaApp - Panel Administracyjny"
admin.site.site_title = "GastronomiaApp Admin"
admin.site.index_title = "Witaj w panelu administracyjnym GastronomiaApp"

# Dodaj custom CSS dla admin interface
admin.site.enable_nav_sidebar = False  # Wyłącz sidebar w nowszych wersjach Django