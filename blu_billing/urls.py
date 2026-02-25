from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    # Billing Overview
    path('overview/', views.superadmin_billing_overview, name='superadmin_billing_overview'),
    
    # Subscription Management
    path('subscriptions/', views.CompanySubscriptionListView.as_view(), name='superadmin_subscriptions'),
    path('subscriptions/<int:pk>/', views.CompanySubscriptionDetailView.as_view(), name='subscription_detail'),
    path('subscriptions/<int:pk>/update-status/', views.update_subscription_status, name='update_subscription_status'),
    path('subscriptions/<int:pk>/generate-invoice/', views.generate_invoice, name='generate_invoice'),
    
    # Subscription Plans
    path('plans/', views.SubscriptionPlanListView.as_view(), name='superadmin_plans'),
    
    # Invoice Management
    path('invoices/', views.superadmin_invoices, name='superadmin_invoices'),
    path('invoices/<int:invoice_id>/', views.superadmin_invoice_detail, name='superadmin_invoice_detail'),
]
