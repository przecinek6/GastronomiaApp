from django.urls import path
from frontend import views

urlpatterns = [
    # Podstawowe strony
    path('', views.home_page, name='home_page'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),
    
    # Panel zarządzania
    path('manage/', views.manage_dashboard, name='manage_dashboard'),
    
    # Zarządzanie składnikami
    path('manage/ingredients/', views.ingredient_list, name='ingredient_list'),
    path('manage/ingredients/add/', views.ingredient_add, name='ingredient_add'),
    path('manage/ingredients/<int:pk>/edit/', views.ingredient_edit, name='ingredient_edit'),
    path('manage/ingredients/<int:pk>/delete/', views.ingredient_delete, name='ingredient_delete'),
]