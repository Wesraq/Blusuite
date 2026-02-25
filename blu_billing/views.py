from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, UpdateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum, Count, Q, Avg, Min, Max
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal

from .models import SubscriptionPlan, CompanySubscription, Invoice, Payment, UsageMetric
from blu_staff.apps.accounts.models import Company, User
from ems_project.frontend_views import _is_superadmin


class SuperAdminRequiredMixin:
    """Mixin to ensure user is SuperAdmin"""
    def dispatch(self, request, *args, **kwargs):
        if not _is_superadmin(request.user):
            messages.error(request, "Access denied. SuperAdmin privileges required.")
            return redirect('ems_login')
        return super().dispatch(request, *args, **kwargs)


@login_required
def superadmin_billing_overview(request):
    """Comprehensive billing overview for SuperAdmin"""
    if not _is_superadmin(request.user):
        return render(request, 'ems/unauthorized.html')
    
    today = timezone.now().date()
    month_start = today.replace(day=1)
    month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    # Subscription metrics
    subscription_stats = CompanySubscription.objects.aggregate(
        total_active=Count('id', filter=Q(status='ACTIVE')),
        total_trial=Count('id', filter=Q(status='TRIAL')),
        total_suspended=Count('id', filter=Q(status='SUSPENDED')),
        total_expired=Count('id', filter=Q(status='EXPIRED')),
    )
    
    # Revenue metrics
    revenue_this_month = Invoice.objects.filter(
        status='PAID',
        paid_at__year=today.year,
        paid_at__month=today.month
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    
    pending_revenue = Invoice.objects.filter(status='PENDING').aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0.00')
    
    # Monthly revenue trend (last 6 months)
    monthly_revenue = []
    for i in range(6):
        month_date = today.replace(day=1) - timedelta(days=i*30)
        month_revenue = Invoice.objects.filter(
            status='PAID',
            paid_at__year=month_date.year,
            paid_at__month=month_date.month
        ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
        monthly_revenue.append({
            'month': month_date.strftime('%b %Y'),
            'revenue': month_revenue
        })
    
    # Expiring subscriptions
    expiring_soon = CompanySubscription.objects.filter(
        status__in=['ACTIVE', 'TRIAL'],
        current_period_end__isnull=False,
        current_period_end__lte=today + timedelta(days=30)
    ).select_related('company', 'plan')
    
    # Recent invoices
    recent_invoices = Invoice.objects.select_related('company', 'subscription').order_by('-created_at')[:10]
    
    # Top plans by revenue
    top_plans = SubscriptionPlan.objects.annotate(
        revenue=Sum('companysubscription__invoices__total_amount', 
                  filter=Q(companysubscription__invoices__status='PAID'))
    ).order_by('-revenue')[:5]
    
    # Usage metrics
    total_storage = UsageMetric.objects.filter(
        metric_type='storage',
        metric_date=today
    ).aggregate(total=Sum('metric_value'))['total'] or Decimal('0.00')
    
    total_api_calls = UsageMetric.objects.filter(
        metric_type='api_calls',
        metric_date=today
    ).aggregate(total=Sum('metric_value'))['total'] or 0
    
    context = {
        'subscription_stats': subscription_stats,
        'revenue_this_month': revenue_this_month,
        'pending_revenue': pending_revenue,
        'monthly_revenue': monthly_revenue,
        'expiring_soon': expiring_soon,
        'recent_invoices': recent_invoices,
        'top_plans': top_plans,
        'total_storage': total_storage,
        'total_api_calls': total_api_calls,
    }
    
    return render(request, 'blu_billing/superadmin_billing_overview.html', context)


class SubscriptionPlanListView(SuperAdminRequiredMixin, ListView):
    """List all subscription plans"""
    model = SubscriptionPlan
    template_name = 'blu_billing/superadmin_plans.html'
    context_object_name = 'plans'
    
    def get_queryset(self):
        return SubscriptionPlan.objects.annotate(
            active_subscriptions=Count('companysubscription', filter=Q(companysubscription__status='ACTIVE')),
            trial_subscriptions=Count('companysubscription', filter=Q(companysubscription__status='TRIAL'))
        ).order_by('monthly_price')


class CompanySubscriptionListView(SuperAdminRequiredMixin, ListView):
    """List all company subscriptions"""
    model = CompanySubscription
    template_name = 'blu_billing/superadmin_subscriptions.html'
    context_object_name = 'subscriptions'
    paginate_by = 20
    
    def get_queryset(self):
        return CompanySubscription.objects.select_related(
            'company', 'plan'
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filter options
        status_filter = self.request.GET.get('status', '')
        plan_filter = self.request.GET.get('plan', '')
        
        queryset = self.get_queryset()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if plan_filter:
            queryset = queryset.filter(plan_id=plan_filter)
        
        context['subscriptions'] = queryset
        context['status_choices'] = CompanySubscription.Status.choices
        context['plans'] = SubscriptionPlan.objects.all()
        context['status_filter'] = status_filter
        context['plan_filter'] = plan_filter
        
        return context


class CompanySubscriptionDetailView(SuperAdminRequiredMixin, DetailView):
    """Detailed view of a company subscription"""
    model = CompanySubscription
    template_name = 'blu_billing/subscription_detail.html'
    context_object_name = 'subscription'
    
    def get_object(self):
        return get_object_or_404(
            CompanySubscription.objects.select_related('company', 'plan'),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        subscription = context['subscription']
        
        # Get invoices for this subscription
        context['invoices'] = Invoice.objects.filter(
            subscription=subscription
        ).order_by('-created_at')
        
        # Get usage metrics
        context['usage_metrics'] = UsageMetric.objects.filter(
            company=subscription.company
        ).order_by('-metric_date')[:30]
        
        # Calculate usage stats
        context['usage_stats'] = UsageMetric.objects.filter(
            company=subscription.company,
            metric_date__gte=timezone.now().date() - timedelta(days=30)
        ).aggregate(
            avg_storage=Avg('metric_value', filter=Q(metric_type='storage')),
            avg_api_calls=Avg('metric_value', filter=Q(metric_type='api_calls'))
        )
        
        return context


@login_required
def superadmin_invoices(request):
    """List all invoices with filtering"""
    if not _is_superadmin(request.user):
        return render(request, 'ems/unauthorized.html')
    
    invoices = Invoice.objects.select_related('company', 'subscription')
    
    # Filters
    status_filter = request.GET.get('status', '')
    company_filter = request.GET.get('company', '')
    date_filter = request.GET.get('date', '')
    
    if status_filter:
        invoices = invoices.filter(status=status_filter)
    
    if company_filter:
        invoices = invoices.filter(company_id=company_filter)
    
    if date_filter:
        try:
            filter_date = date.fromisoformat(date_filter)
            invoices = invoices.filter(issue_date__date=filter_date)
        except ValueError:
            pass
    
    invoices = invoices.order_by('-created_at')
    
    # Summary stats
    summary = Invoice.objects.aggregate(
        total_invoices=Count('id'),
        paid_invoices=Count('id', filter=Q(status='PAID')),
        pending_invoices=Count('id', filter=Q(status='PENDING')),
        total_amount=Sum('total_amount'),
        paid_amount=Sum('total_amount', filter=Q(status='PAID'))
    )
    
    context = {
        'invoices': invoices,
        'summary': summary,
        'status_choices': Invoice.Status.choices,
        'companies': Company.objects.all(),
        'status_filter': status_filter,
        'company_filter': company_filter,
        'date_filter': date_filter,
    }
    
    return render(request, 'blu_billing/superadmin_invoices.html', context)


@login_required
def superadmin_invoice_detail(request, invoice_id):
    """Detailed view of an invoice"""
    if not _is_superadmin(request.user):
        return render(request, 'ems/unauthorized.html')
    
    invoice = get_object_or_404(
        Invoice.objects.select_related('company', 'subscription'),
        pk=invoice_id
    )
    
    payments = invoice.payments.all()
    
    context = {
        'invoice': invoice,
        'payments': payments,
    }
    
    return render(request, 'blu_billing/invoice_detail.html', context)


@login_required
def update_subscription_status(request, subscription_id):
    """Update subscription status"""
    if not _is_superadmin(request.user):
        return render(request, 'ems/unauthorized.html')
    
    if request.method == 'POST':
        subscription = get_object_or_404(CompanySubscription, pk=subscription_id)
        new_status = request.POST.get('status')
        
        if new_status in dict(CompanySubscription.Status.choices):
            old_status = subscription.status
            subscription.status = new_status
            
            # Handle status transitions
            if new_status == 'ACTIVE' and old_status != 'ACTIVE':
                subscription.current_period_start = timezone.now()
                subscription.current_period_end = timezone.now() + timedelta(days=30)
                subscription.next_billing_date = subscription.current_period_end
            elif new_status == 'CANCELLED':
                subscription.current_period_end = timezone.now()
            
            subscription.save()
            messages.success(request, f'Subscription status updated to {new_status}')
        else:
            messages.error(request, 'Invalid status')
    
    return redirect('superadmin_subscriptions')


@login_required
def generate_invoice(request, subscription_id):
    """Generate a new invoice for a subscription"""
    if not _is_superadmin(request.user):
        return render(request, 'ems/unauthorized.html')
    
    subscription = get_object_or_404(
        CompanySubscription.objects.select_related('company', 'plan'),
        pk=subscription_id
    )
    
    if request.method == 'POST':
        # Create new invoice
        amount = subscription.plan.get_price_for_cycle(subscription.billing_cycle)
        tax_amount = amount * Decimal('0.10')  # 10% tax
        total_amount = amount + tax_amount
        
        invoice = Invoice.objects.create(
            company=subscription.company,
            subscription=subscription,
            amount=amount,
            tax_amount=tax_amount,
            total_amount=total_amount,
            issue_date=timezone.now(),
            due_date=timezone.now() + timedelta(days=30),
            status='PENDING'
        )
        
        messages.success(request, f'Invoice {invoice.invoice_number} generated successfully')
        return redirect('superadmin_invoice_detail', invoice_id=invoice.id)
    
    context = {
        'subscription': subscription,
    }
    
    return render(request, 'blu_billing/generate_invoice.html', context)
