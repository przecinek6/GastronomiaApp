from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout, get_user_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from frontend.models import UserProfile
from frontend.forms import CustomRegistrationForm, CustomLoginForm

User = get_user_model()

def home_page(request):
    return render(request, 'home.html')

def register_view(request):
    if request.user.is_authenticated:
        return redirect('home_page')
    
    if request.method == 'POST':
        form = CustomRegistrationForm(request.POST)
        
        if form.is_valid():
            try:
                user = form.save()
                
                messages.success(request, 'Rejestracja przebiegła pomyślnie! Możesz się teraz zalogować.')

                return redirect('login_view')
            except Exception as e:
                import traceback
                traceback.print_exc()
                messages.error(request, f'Wystąpił błąd podczas rejestracji: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = CustomRegistrationForm()
    
    return render(request, 'auth/register.html', {'form': form})

def login_view(request):
    if request.user.is_authenticated:
        return redirect('home_page')
    
    if request.method == 'POST':
        form = CustomLoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data['username']
            password = form.cleaned_data['password']
            remember_me = form.cleaned_data.get('remember_me', False)
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Ustaw długość sesji w zależności od "Zapamiętaj mnie"
                if not remember_me:
                    request.session.set_expiry(0)
                else:
                    request.session.set_expiry(1209600)  # 2 tygodnie
                
                messages.success(request, f'Witaj ponownie, {user.first_name or user.username}!')
                
                # Przekieruj w zależności od roli
                try:
                    if user.userprofile.role == 'manager':
                        return redirect('admin:index')
                    else:
                        return redirect('home_page')
                except UserProfile.DoesNotExist:
                    UserProfile.objects.create(user=user, role='client')
                    return redirect('home_page')
            else:
                messages.error(request, 'Nieprawidłowe dane logowania.')
    else:
        form = CustomLoginForm()
    
    return render(request, 'auth/login.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    messages.success(request, 'Zostałeś pomyślnie wylogowany. Do zobaczenia!')
    return redirect('home_page')