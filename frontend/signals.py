from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from frontend.models import UserProfile, LoyaltyAccount

User = get_user_model()

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Automatycznie tworzy UserProfile i LoyaltyAccount dla nowego użytkownika
    """
    if created:
        try:
            # Sprawdź czy profil już istnieje
            if not UserProfile.objects.filter(user=instance).exists():
                UserProfile.objects.create(
                    user=instance,
                    role='client'
                )
            
            # Sprawdź czy konto lojalnościowe już istnieje
            if not LoyaltyAccount.objects.filter(user=instance).exists():
                LoyaltyAccount.objects.create(
                    user=instance,
                    points_balance=0,
                    total_points_earned=0,
                    loyalty_level='bronze'
                )
        except Exception as e:
            # Jeśli wystąpi błąd w sygnałach, wyloguj go ale nie przerywaj procesu
            print(f"Błąd w sygnałach podczas tworzenia profilu: {e}")