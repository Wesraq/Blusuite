from django.urls import path
from . import views

app_name = 'payments'

urlpatterns = [
    path('plans/', views.payment_plans, name='plans'),
    path('create-checkout-session/', views.create_checkout_session, name='create_checkout_session'),
    path('success/', views.payment_success, name='success'),
    path('registration-success/', views.registration_success, name='registration_success'),
    path('webhook/', views.stripe_webhook, name='webhook'),
    path('billing/', views.company_billing, name='billing'),
]
