from django.urls import path
from frontend import views

urlpatterns = [
    path('', views.home_page, name='home_page'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login_view'),
    path('logout/', views.logout_view, name='logout_view'),
]