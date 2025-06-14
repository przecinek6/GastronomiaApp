from django.urls import path
from frontend import views

urlpatterns = [
    # Podstawowe strony
    path('', views.home_page, name='home_page'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),
    
    # Panel klienta
    path('dashboard/', views.client_dashboard, name='client_dashboard'),
    path('profile/', views.client_profile, name='client_profile'),

    # Przeglądanie planów dietetycznych (klienci)
    path('plans/', views.browse_diet_plans, name='browse_diet_plans'),
    path('plans/<int:pk>/', views.diet_plan_detail, name='diet_plan_detail'),
    path('plans/compare/', views.compare_diet_plans, name='compare_diet_plans'),

    # Moduł subskrypcji klienta
    path('subscriptions/<uuid:subscription_id>/', views.subscription_detail, name='subscription_detail'),
    path('subscriptions/create/<int:plan_id>/', views.subscription_create, name='subscription_create'),
    path('subscriptions/<uuid:subscription_id>/pause/', views.subscription_pause, name='subscription_pause'),
    path('subscriptions/<uuid:subscription_id>/cancel/', views.subscription_cancel, name='subscription_cancel'),
    path('subscriptions/<uuid:subscription_id>/change-diet/', views.diet_change, name='diet_change'),
    
    path('my-payments/', views.client_payments, name='client_payments'),

    # Panel zarządzania
    path('manage/', views.manage_dashboard, name='manage_dashboard'),
    
    # Zarządzanie składnikami
    path('manage/ingredients/', views.ingredient_list, name='ingredient_list'),
    path('manage/ingredients/add/', views.ingredient_add, name='ingredient_add'),
    path('manage/ingredients/<int:pk>/edit/', views.ingredient_edit, name='ingredient_edit'),
    path('manage/ingredients/<int:pk>/delete/', views.ingredient_delete, name='ingredient_delete'),
    
    # Zarządzanie daniami
    path('manage/dishes/', views.dish_list, name='dish_list'),
    path('manage/dishes/add/', views.dish_add, name='dish_add'),
    path('manage/dishes/<int:pk>/edit/', views.dish_edit, name='dish_edit'),
    path('manage/dishes/<int:pk>/delete/', views.dish_delete, name='dish_delete'),
    
    # Zarządzanie planami dietetycznymi  
    path('manage/diet-plans/', views.diet_plan_list, name='diet_plan_list'),
    path('manage/diet-plans/add/', views.diet_plan_add, name='diet_plan_add'),
    path('manage/diet-plans/<int:pk>/edit/', views.diet_plan_edit, name='diet_plan_edit'),
    path('manage/diet-plans/<int:pk>/delete/', views.diet_plan_delete, name='diet_plan_delete'),

    # Zarzadzanie zakupami
    path('manage/shopping/', views.shopping_list_overview, name='shopping_list_overview'),
    path('manage/shopping/preview/<int:year>/<int:month>/<int:day>/', views.shopping_list_preview, name='shopping_list_preview'),
    path('manage/shopping/pdf/<int:year>/<int:month>/<int:day>/', views.shopping_list_pdf, name='shopping_list_pdf'),

    # API endpointy
    path('api/ingredient/<int:ingredient_id>/', views.ingredient_data_api, name='ingredient_data_api'),
    path('api/ingredients/', views.ingredients_list_api, name='ingredients_list_api'),
    path('api/dish/<int:dish_id>/', views.dish_detail_api, name='dish_detail_api'),
]