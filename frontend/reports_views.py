# frontend/reports_views.py
import json
from datetime import datetime, timedelta, date
from decimal import Decimal
from collections import defaultdict, Counter

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg, F, Q, Case, When, IntegerField
from django.db.models.functions import TruncMonth, TruncWeek, TruncDate
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_GET

import os
from django.conf import settings

# ReportLab do generowania PDF
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_RIGHT

from frontend.models import (
    UserProfile, Subscription, Payment, DietPlan, 
    DietChange, ReferralProgram, Dish, Ingredient
)
from frontend.views import user_is_manager


@login_required
def reports_dashboard(request):
    """Dashboard z przeglądem wszystkich raportów"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Pobierz podstawowe statystyki
    today = timezone.now().date()
    current_month_start = today.replace(day=1)
    current_year_start = today.replace(month=1, day=1)
    
    # Statystyki przychodów
    revenue_stats = {
        'today': Payment.objects.filter(
            payment_date=today,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        
        'this_month': Payment.objects.filter(
            payment_date__gte=current_month_start,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
        
        'this_year': Payment.objects.filter(
            payment_date__gte=current_year_start,
            status='completed'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0'),
    }
    
    # Statystyki subskrypcji
    subscription_stats = {
        'active': Subscription.objects.filter(status='active').count(),
        'new_this_month': Subscription.objects.filter(
            created_at__gte=current_month_start
        ).count(),
        'cancelled_this_month': Subscription.objects.filter(
            status='cancelled',
            updated_at__gte=current_month_start
        ).count(),
    }
    
    # Najpopularniejsze plany
    popular_plans = DietPlan.objects.annotate(
        subscription_count=Count('subscription')
    ).order_by('-subscription_count')[:5]
    
    context = {
        'revenue_stats': revenue_stats,
        'subscription_stats': subscription_stats,
        'popular_plans': popular_plans,
        'current_date': today,
    }
    
    return render(request, 'management/reports/dashboard.html', context)


@login_required
def revenue_report(request):
    """Szczegółowy raport przychodów"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Parametry z GET
    period = request.GET.get('period', 'month')  # week, month, year
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Ustaw domyślne daty
    today = timezone.now().date()
    if not end_date:
        end_date = today
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    if not start_date:
        if period == 'week':
            start_date = end_date - timedelta(days=7)
        elif period == 'month':
            start_date = end_date - timedelta(days=30)
        else:  # year
            start_date = end_date - timedelta(days=365)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    # Pobierz dane o płatnościach
    payments = Payment.objects.filter(
        payment_date__gte=start_date,
        payment_date__lte=end_date,
        status='completed'
    )
    
    # Statystyki ogólne
    total_revenue = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    payment_count = payments.count()
    avg_payment = payments.aggregate(avg=Avg('amount'))['avg'] or Decimal('0')
    
    # Przychody według planów dietetycznych
    revenue_by_plan = payments.values(
        'subscription__diet_plan__name'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Przychody w czasie
    if period == 'week':
        revenue_over_time = payments.annotate(
            period=TruncDate('payment_date')
        ).values('period').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('period')
    elif period == 'month':
        revenue_over_time = payments.annotate(
            period=TruncWeek('payment_date')
        ).values('period').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('period')
    else:  # year
        revenue_over_time = payments.annotate(
            period=TruncMonth('payment_date')
        ).values('period').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('period')
    
    # Przygotuj dane dla wykresu
    chart_data = {
        'labels': [item['period'].strftime('%Y-%m-%d') for item in revenue_over_time],
        'revenue': [float(item['total']) for item in revenue_over_time],
        'count': [item['count'] for item in revenue_over_time],
    }
    
    context = {
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
        'total_revenue': total_revenue,
        'payment_count': payment_count,
        'avg_payment': avg_payment,
        'revenue_by_plan': revenue_by_plan,
        'chart_data': json.dumps(chart_data),
    }
    
    return render(request, 'management/reports/revenue.html', context)


@login_required
def subscription_analytics(request):
    """Analiza subskrypcji i retencji klientów"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Pobierz wszystkie subskrypcje
    subscriptions = Subscription.objects.all()
    
    # Status subskrypcji
    status_distribution = subscriptions.values('status').annotate(
        count=Count('id')
    ).order_by('status')
    
    # Czas trwania subskrypcji
    duration_distribution = subscriptions.values('duration').annotate(
        count=Count('id')
    ).order_by('duration')
    
    # Średni czas trwania aktywnych subskrypcji
    active_subscriptions = subscriptions.filter(
        Q(status='active') | Q(status='completed')
    )
    
    subscription_durations = []
    for sub in active_subscriptions:
        if sub.status == 'completed':
            duration = (sub.end_date - sub.start_date).days
        else:
            duration = (timezone.now().date() - sub.start_date).days
        subscription_durations.append(duration)
    
    avg_duration = sum(subscription_durations) / len(subscription_durations) if subscription_durations else 0
    
    # Współczynnik retencji (procent subskrypcji które nie zostały anulowane)
    total_subs = subscriptions.count()
    cancelled_subs = subscriptions.filter(status='cancelled').count()
    retention_rate = ((total_subs - cancelled_subs) / total_subs * 100) if total_subs > 0 else 0
    
    # Analiza zmian diet
    diet_changes = DietChange.objects.filter(status='completed')
    avg_changes_per_sub = diet_changes.values('subscription').annotate(
        changes=Count('id')
    ).aggregate(avg=Avg('changes'))['avg'] or 0
    
    # Najpopularniejsze zmiany diet
    diet_change_patterns = diet_changes.values(
        'old_plan__name', 'new_plan__name'
    ).annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    # Przyczyny rezygnacji (na podstawie anulowanych subskrypcji z ostatniego miesiąca)
    last_month = timezone.now().date() - timedelta(days=30)
    recent_cancellations = subscriptions.filter(
        status='cancelled',
        updated_at__gte=last_month
    )
    
    # Analiza długości subskrypcji przed anulowaniem
    cancellation_timing = defaultdict(int)
    for sub in recent_cancellations:
        days_active = (sub.updated_at.date() - sub.start_date).days
        if days_active < 7:
            cancellation_timing['Pierwszy tydzień'] += 1
        elif days_active < 30:
            cancellation_timing['Pierwszy miesiąc'] += 1
        elif days_active < 90:
            cancellation_timing['1-3 miesiące'] += 1
        else:
            cancellation_timing['Ponad 3 miesiące'] += 1
    
    context = {
        'status_distribution': status_distribution,
        'duration_distribution': duration_distribution,
        'avg_duration': avg_duration,
        'retention_rate': retention_rate,
        'avg_changes_per_sub': avg_changes_per_sub,
        'diet_change_patterns': diet_change_patterns,
        'cancellation_timing': dict(cancellation_timing),
        'total_subscriptions': total_subs,
        'active_subscriptions': subscriptions.filter(status='active').count(),
    }
    
    return render(request, 'management/reports/subscriptions.html', context)


@login_required
def customer_insights(request):
    """Analiza zachowań klientów"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Top klienci według wartości
    top_customers = UserProfile.objects.filter(
        role='client'
    ).annotate(
        total_spent=Sum(
            'user__subscriptions__payments__amount',
            filter=Q(user__subscriptions__payments__status='completed')
        ),
        subscription_count=Count('user__subscriptions'),
        active_subscriptions=Count(
            'user__subscriptions',
            filter=Q(user__subscriptions__status='active')
        )
    ).exclude(
        total_spent__isnull=True
    ).order_by('-total_spent')[:20]
    
    # Analiza programu poleceń
    referral_stats = {
        'total_referrals': ReferralProgram.objects.count(),
        'completed_referrals': ReferralProgram.objects.filter(status='completed').count(),
        'pending_referrals': ReferralProgram.objects.filter(status='pending').count(),
        'top_referrers': UserProfile.objects.filter(
            user__referrals_made__status='completed'
        ).annotate(
            referral_count=Count('user__referrals_made')
        ).order_by('-referral_count')[:10]
    }
    
    # Analiza lokalizacji (miasta)
    customer_locations = UserProfile.objects.filter(
        role='client',
        delivery_city__isnull=False
    ).exclude(
        delivery_city=''
    ).values('delivery_city').annotate(
        count=Count('id')
    ).order_by('-count')[:15]
    
    # Średnia wartość zamówienia według długości subskrypcji
    avg_order_by_duration = Payment.objects.filter(
        status='completed'
    ).values(
        'subscription__duration'
    ).annotate(
        avg_amount=Avg('amount'),
        total_amount=Sum('amount'),
        count=Count('id')
    ).order_by('subscription__duration')
    
    context = {
        'top_customers': top_customers,
        'referral_stats': referral_stats,
        'customer_locations': customer_locations,
        'avg_order_by_duration': avg_order_by_duration,
    }
    
    return render(request, 'management/reports/customers.html', context)


@login_required
def inventory_analysis(request):
    """Analiza wykorzystania składników i popularności dań"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Najpopularniejsze dania (na podstawie planów posiłków w aktywnych subskrypcjach)
    active_plans = DietPlan.objects.filter(
        subscription__status='active'
    ).distinct()
    
    dish_popularity = Dish.objects.filter(
        mealplan__diet_plan__in=active_plans
    ).annotate(
        usage_count=Count('mealplan')
    ).order_by('-usage_count')[:20]
    
    # Najczęściej używane składniki
    ingredient_usage = Ingredient.objects.filter(
        dishingredient__dish__in=dish_popularity
    ).annotate(
        usage_count=Count('dishingredient'),
        total_quantity=Sum('dishingredient__quantity_grams')
    ).order_by('-usage_count')[:20]
    
    # Analiza kosztów składników
    expensive_ingredients = Ingredient.objects.filter(
        is_deleted=False
    ).order_by('-price_per_100g')[:10]
    
    # Dania według wartości odżywczych
    nutritional_analysis = {
        'high_protein': Dish.objects.filter(is_deleted=False).annotate(
            calculated_protein=Sum(
                F('dishingredient__ingredient__protein_per_100g') * 
                F('dishingredient__quantity_grams') / 100
            )
        ).order_by('-calculated_protein')[:10],
        
        'low_calorie': Dish.objects.filter(is_deleted=False).annotate(
            calculated_calories=Sum(
                F('dishingredient__ingredient__calories_per_100g') * 
                F('dishingredient__quantity_grams') / 100
            )
        ).order_by('calculated_calories')[:10],
    }
    
    context = {
        'dish_popularity': dish_popularity,
        'ingredient_usage': ingredient_usage,
        'expensive_ingredients': expensive_ingredients,
        'nutritional_analysis': nutritional_analysis,
    }
    
    return render(request, 'management/reports/inventory.html', context)


@login_required 
def generate_report_pdf(request, report_type):
    """Generowanie raportu PDF"""
    if not user_is_manager(request.user):
        messages.error(request, 'Nie masz uprawnień do tej strony.')
        return redirect('home_page')
    
    # Sprawdź typ raportu
    valid_types = ['revenue', 'subscriptions', 'customers', 'inventory']
    if report_type not in valid_types:
        messages.error(request, 'Nieprawidłowy typ raportu.')
        return redirect('reports_dashboard')
    
    # Parametry z GET
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Ustaw domyślne daty
    if not end_date:
        end_date = timezone.now().date()
    else:
        end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    
    if not start_date:
        start_date = end_date - timedelta(days=30)
    else:
        start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
    
    # Przygotuj response
    filename = f"raport_{report_type}_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.pdf"
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    # Rejestracja fontu wspierającego polskie znaki
    try:
        font_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'fonts', 'DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        font_name = 'DejaVuSans'
    except Exception as e:
        print(f"Błąd ładowania fontu: {e}")
        font_name = 'Helvetica'
    
    # Utwórz dokument PDF
    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=18,
    )
    
    # Kontener na elementy
    story = []
    
    # Style
    styles = getSampleStyleSheet()
    
    # Aktualizuj wszystkie style żeby używały fontu z polskimi znakami
    for style_name, style in styles.byName.items():
        if hasattr(style, 'fontName'):
            style.fontName = font_name
    
    # Nagłówek
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontName=font_name,
        fontSize=24,
        textColor=colors.HexColor('#1f2937'),
        spaceAfter=30,
        alignment=TA_CENTER,
    )
    
    # Tytuł raportu
    report_titles = {
        'revenue': 'Raport przychodów',
        'subscriptions': 'Analiza subskrypcji',
        'customers': 'Analiza klientów',
        'inventory': 'Analiza składników i dań'
    }
    
    title = Paragraph(report_titles[report_type], title_style)
    story.append(title)
    
    # Data raportu
    date_style = ParagraphStyle(
        'DateStyle',
        parent=styles['Normal'],
        fontName=font_name,
        fontSize=12,
        textColor=colors.HexColor('#6b7280'),
        spaceAfter=20,
        alignment=TA_CENTER,
    )
    date_text = f"Okres: {start_date.strftime('%d.%m.%Y')} - {end_date.strftime('%d.%m.%Y')}"
    story.append(Paragraph(date_text, date_style))
    story.append(Spacer(1, 20))
    
    # Generuj zawartość w zależności od typu
    if report_type == 'revenue':
        _generate_revenue_pdf_content(story, styles, start_date, end_date)
    elif report_type == 'subscriptions':
        _generate_subscriptions_pdf_content(story, styles)
    elif report_type == 'customers':
        _generate_customers_pdf_content(story, styles)
    elif report_type == 'inventory':
        _generate_inventory_pdf_content(story, styles)
    
    # Buduj PDF
    doc.build(story)
    return response


def _generate_revenue_pdf_content(story, styles, start_date, end_date):
    """Generuj zawartość PDF dla raportu przychodów"""
    # Rejestracja fontu wspierającego polskie znaki
    try:
        font_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'fonts', 'DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        font_name = 'DejaVuSans'
    except Exception as e:
        print(f"Błąd ładowania fontu: {e}")
        font_name = 'Helvetica'
    
    # Aktualizuj style żeby używały właściwego fontu
    for style in styles.byName.values():
        if hasattr(style, 'fontName'):
            style.fontName = font_name
    
    # Pobierz dane
    payments = Payment.objects.filter(
        payment_date__gte=start_date,
        payment_date__lte=end_date,
        status='completed'
    )
    
    total_revenue = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    payment_count = payments.count()
    
    # Podsumowanie
    summary_data = [
        ['Całkowity przychód:', f'{total_revenue:.2f} zł'],
        ['Liczba płatności:', str(payment_count)],
        ['Średnia wartość:', f'{(total_revenue/payment_count if payment_count > 0 else 0):.2f} zł'],
    ]
    
    summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.white),
    ]))
    
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # Przychody według planów
    story.append(Paragraph("Przychody według planów dietetycznych", styles['Heading2']))
    
    revenue_by_plan = payments.values(
        'subscription__diet_plan__name'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')[:10]
    
    plan_data = [['Plan dietetyczny', 'Przychód', 'Liczba płatności']]
    for item in revenue_by_plan:
        plan_data.append([
            item['subscription__diet_plan__name'] or 'Nieznany',
            f"{item['total']:.2f} zł",
            str(item['count'])
        ])
    
    plan_table = Table(plan_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
    plan_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(plan_table)


def _generate_subscriptions_pdf_content(story, styles):
    """Generuj zawartość PDF dla analizy subskrypcji"""
    # Rejestracja fontu wspierającego polskie znaki
    try:
        font_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'fonts', 'DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        font_name = 'DejaVuSans'
    except Exception as e:
        font_name = 'Helvetica'
    
    subscriptions = Subscription.objects.all()
    total = subscriptions.count()
    active = subscriptions.filter(status='active').count()
    
    # Statystyki
    story.append(Paragraph("Statystyki subskrypcji", styles['Heading2']))
    
    stats_data = [
        ['Całkowita liczba subskrypcji:', str(total)],
        ['Aktywne subskrypcje:', str(active)],
        ['Współczynnik retencji:', f'{(active/total*100 if total > 0 else 0):.1f}%'],
    ]
    
    stats_table = Table(stats_data, colWidths=[3*inch, 2*inch])
    stats_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    story.append(stats_table)
    story.append(Spacer(1, 20))
    
    # Dystrybucja statusów
    story.append(Paragraph("Dystrybucja statusów", styles['Heading3']))
    
    status_dist = subscriptions.values('status').annotate(count=Count('id'))
    status_data = [['Status', 'Liczba']]
    
    status_labels = {
        'pending': 'Oczekująca',
        'active': 'Aktywna', 
        'paused': 'Wstrzymana',
        'cancelled': 'Anulowana',
        'completed': 'Zakończona'
    }
    
    for item in status_dist:
        status_data.append([
            status_labels.get(item['status'], item['status']),
            str(item['count'])
        ])
    
    status_table = Table(status_data, colWidths=[2*inch, 1*inch])
    status_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(status_table)


def _generate_customers_pdf_content(story, styles):
    """Generuj zawartość PDF dla analizy klientów"""
    # Rejestracja fontu wspierającego polskie znaki
    try:
        font_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'fonts', 'DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        font_name = 'DejaVuSans'
    except Exception as e:
        font_name = 'Helvetica'
    
    # Top klienci
    story.append(Paragraph("Top 10 klientów według wartości", styles['Heading2']))
    
    top_customers = UserProfile.objects.filter(
        role='client'
    ).annotate(
        total_spent=Sum(
            'user__subscriptions__payments__amount',
            filter=Q(user__subscriptions__payments__status='completed')
        )
    ).exclude(
        total_spent__isnull=True
    ).order_by('-total_spent')[:10]
    
    customer_data = [['Klient', 'Wartość zamówień']]
    for customer in top_customers:
        customer_data.append([
            f"{customer.user.first_name} {customer.user.last_name}".strip() or customer.user.username,
            f"{customer.total_spent:.2f} zł"
        ])
    
    customer_table = Table(customer_data, colWidths=[3*inch, 2*inch])
    customer_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(customer_table)


def _generate_inventory_pdf_content(story, styles):
    """Generuj zawartość PDF dla analizy składników"""
    # Rejestracja fontu wspierającego polskie znaki
    try:
        font_path = os.path.join(settings.STATIC_ROOT or settings.BASE_DIR, 'fonts', 'DejaVuSans.ttf')
        pdfmetrics.registerFont(TTFont('DejaVuSans', font_path))
        font_name = 'DejaVuSans'
    except Exception as e:
        font_name = 'Helvetica'
    
    # Najpopularniejsze dania
    story.append(Paragraph("Top 10 najpopularniejszych dań", styles['Heading2']))
    
    dish_popularity = Dish.objects.annotate(
        usage_count=Count('mealplan')
    ).order_by('-usage_count')[:10]
    
    dish_data = [['Danie', 'Liczba użyć']]
    for dish in dish_popularity:
        dish_data.append([
            dish.name,
            str(dish.usage_count)
        ])
    
    dish_table = Table(dish_data, colWidths=[4*inch, 1.5*inch])
    dish_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), font_name),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    
    story.append(dish_table)


# API endpoints dla wykresów
@login_required
@require_GET
def revenue_chart_data(request):
    """Dane do wykresu przychodów"""
    if not user_is_manager(request.user):
        return JsonResponse({'error': 'Brak uprawnień'}, status=403)
    
    period = request.GET.get('period', 'month')
    end_date = timezone.now().date()
    
    if period == 'week':
        start_date = end_date - timedelta(days=7)
        payments = Payment.objects.filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date,
            status='completed'
        ).annotate(
            day=TruncDate('payment_date')
        ).values('day').annotate(
            total=Sum('amount')
        ).order_by('day')
        
        labels = [(start_date + timedelta(days=i)).strftime('%d.%m') for i in range(8)]
        data = {label: 0 for label in labels}
        
        for payment in payments:
            label = payment['day'].strftime('%d.%m')
            if label in data:
                data[label] = float(payment['total'])
        
    elif period == 'month':
        start_date = end_date - timedelta(days=30)
        payments = Payment.objects.filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date,
            status='completed'
        ).annotate(
            week=TruncWeek('payment_date')
        ).values('week').annotate(
            total=Sum('amount')
        ).order_by('week')
        
        labels = []
        current = start_date
        while current <= end_date:
            labels.append(current.strftime('%d.%m'))
            current += timedelta(days=7)
        
        data = {label: 0 for label in labels}
        
        for payment in payments:
            label = payment['week'].strftime('%d.%m')
            closest_label = min(labels, key=lambda x: abs(datetime.strptime(x, '%d.%m').replace(year=payment['week'].year) - payment['week']))
            data[closest_label] += float(payment['total'])
    
    else:  # year
        start_date = end_date - timedelta(days=365)
        payments = Payment.objects.filter(
            payment_date__gte=start_date,
            payment_date__lte=end_date,
            status='completed'
        ).annotate(
            month=TruncMonth('payment_date')
        ).values('month').annotate(
            total=Sum('amount')
        ).order_by('month')
        
        labels = []
        current = start_date.replace(day=1)
        while current <= end_date:
            labels.append(current.strftime('%m.%Y'))
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1)
            else:
                current = current.replace(month=current.month + 1)
        
        data = {label: 0 for label in labels}
        
        for payment in payments:
            label = payment['month'].strftime('%m.%Y')
            if label in data:
                data[label] = float(payment['total'])
    
    return JsonResponse({
        'labels': list(data.keys()),
        'values': list(data.values()),
    })


@login_required
@require_GET
def subscription_status_data(request):
    """Dane do wykresu statusów subskrypcji"""
    if not user_is_manager(request.user):
        return JsonResponse({'error': 'Brak uprawnień'}, status=403)
    
    status_data = Subscription.objects.values('status').annotate(
        count=Count('id')
    )
    
    status_labels = {
        'pending': 'Oczekujące',
        'active': 'Aktywne',
        'paused': 'Wstrzymane',
        'cancelled': 'Anulowane',
        'completed': 'Zakończone'
    }
    
    labels = []
    values = []
    colors = {
        'pending': '#FCD34D',
        'active': '#34D399',
        'paused': '#60A5FA',
        'cancelled': '#F87171',
        'completed': '#A78BFA'
    }
    
    for item in status_data:
        labels.append(status_labels.get(item['status'], item['status']))
        values.append(item['count'])
    
    return JsonResponse({
        'labels': labels,
        'values': values,
        'colors': [colors.get(item['status'], '#9CA3AF') for item in status_data]
    })


@login_required
@require_GET
def popular_plans_data(request):
    """Dane do wykresu popularności planów"""
    if not user_is_manager(request.user):
        return JsonResponse({'error': 'Brak uprawnień'}, status=403)
    
    plans = DietPlan.objects.annotate(
        subscription_count=Count('subscription')
    ).order_by('-subscription_count')[:10]
    
    labels = []
    values = []
    
    for plan in plans:
        labels.append(plan.name)
        values.append(plan.subscription_count)
    
    return JsonResponse({
        'labels': labels,
        'values': values,
    })


@login_required
@require_GET
def customer_growth_data(request):
    """Dane do wykresu wzrostu liczby klientów"""
    if not user_is_manager(request.user):
        return JsonResponse({'error': 'Brak uprawnień'}, status=403)
    
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=180)  # 6 miesięcy
    
    # Grupuj nowych klientów po miesiącach
    new_customers = UserProfile.objects.filter(
        role='client',
        created_at__gte=start_date
    ).annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')
    
    labels = []
    new_values = []
    total_values = []
    
    total = UserProfile.objects.filter(
        role='client',
        created_at__lt=start_date
    ).count()
    
    for item in new_customers:
        labels.append(item['month'].strftime('%m.%Y'))
        new_values.append(item['count'])
        total += item['count']
        total_values.append(total)
    
    return JsonResponse({
        'labels': labels,
        'new_customers': new_values,
        'total_customers': total_values,
    })