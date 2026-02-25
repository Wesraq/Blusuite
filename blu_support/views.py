from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.contrib import messages
from django.db.models import Sum, Count, Q, Avg, F, Min, Max
from django.utils import timezone
from datetime import date, timedelta
from django.urls import reverse_lazy

from .models import (
    SupportTicket, TicketResponse, SupportCategory, SupportTeam, 
    ServiceLevelAgreement, SatisfactionSurvey
)
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
def superadmin_support_center(request):
    """Comprehensive support center for SuperAdmin"""
    if not _is_superadmin(request.user):
        return render(request, 'ems/unauthorized.html')
    
    today = timezone.now().date()
    
    # Ticket metrics
    ticket_stats = SupportTicket.objects.aggregate(
        total_tickets=Count('id'),
        open_tickets=Count('id', filter=Q(status='OPEN')),
        in_progress_tickets=Count('id', filter=Q(status='IN_PROGRESS')),
        resolved_tickets=Count('id', filter=Q(status='RESOLVED')),
        urgent_tickets=Count('id', filter=Q(priority='URGENT')),
    )
    
    # Recent tickets
    recent_tickets = SupportTicket.objects.select_related(
        'company', 'created_by'
    ).order_by('-created_at')[:10]
    
    # Team performance
    team_stats = SupportTeam.objects.select_related('user').annotate(
        current_workload=Count('user__created_support_tickets', 
                           filter=Q(user__created_support_tickets__status__in=['OPEN', 'IN_PROGRESS']))
    ).order_by('-tickets_resolved')
    
    # Category breakdown
    category_stats = SupportTicket.objects.values('category').annotate(
        ticket_count=Count('id')
    ).order_by('-ticket_count')
    
    # Response time metrics
    avg_response_time = SupportTicket.objects.filter(
        status='RESOLVED'
    ).aggregate(
        avg_time=Avg(F('updated_at') - F('created_at'))
    )['avg_time']
    
    # Satisfaction metrics
    satisfaction_stats = SatisfactionSurvey.objects.aggregate(
        avg_rating=Avg('rating'),
        total_surveys=Count('id'),
        would_recommend_rate=Avg('would_recommend', filter=Q(would_recommend__isnull=False))
    )
    
    # SLA compliance
    sla_compliance = SupportTicket.objects.filter(
        status='RESOLVED'
    ).aggregate(
        resolved_within_sla=Count('id', filter=Q(updated_at__lte=F('created_at') + timedelta(hours=24))),
        total_resolved=Count('id')
    )
    
    context = {
        'ticket_stats': ticket_stats,
        'recent_tickets': recent_tickets,
        'team_stats': team_stats,
        'category_stats': category_stats,
        'avg_response_time': avg_response_time,
        'satisfaction_stats': satisfaction_stats,
        'sla_compliance': sla_compliance,
    }
    
    return render(request, 'blu_support/superadmin_support_center.html', context)


class SupportTicketListView(SuperAdminRequiredMixin, ListView):
    """List all support tickets with filtering"""
    model = SupportTicket
    template_name = 'blu_support/superadmin_tickets.html'
    context_object_name = 'tickets'
    paginate_by = 25
    
    def get_queryset(self):
        return SupportTicket.objects.select_related(
            'company', 'created_by'
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Filters
        status_filter = self.request.GET.get('status', '')
        priority_filter = self.request.GET.get('priority', '')
        category_filter = self.request.GET.get('category', '')
        company_filter = self.request.GET.get('company', '')
        search_query = self.request.GET.get('search', '')
        
        queryset = self.get_queryset()
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if priority_filter:
            queryset = queryset.filter(priority=priority_filter)
        
        if category_filter:
            queryset = queryset.filter(category=category_filter)
        
        if company_filter:
            queryset = queryset.filter(company_id=company_filter)
        
        if search_query:
            queryset = queryset.filter(
                Q(subject__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(company__name__icontains=search_query) |
                Q(created_by__email__icontains=search_query)
            )
        
        context['tickets'] = queryset
        context['status_choices'] = SupportTicket.Status.choices
        context['priority_choices'] = SupportTicket.Priority.choices
        context['categories'] = SupportCategory.objects.all()
        context['companies'] = Company.objects.all()
        context['status_filter'] = status_filter
        context['priority_filter'] = priority_filter
        context['category_filter'] = category_filter
        context['company_filter'] = company_filter
        context['search_query'] = search_query
        
        return context


class SupportTicketDetailView(SuperAdminRequiredMixin, DetailView):
    """Detailed view of a support ticket"""
    model = SupportTicket
    template_name = 'blu_support/ticket_detail.html'
    context_object_name = 'ticket'
    
    def get_object(self):
        return get_object_or_404(
            SupportTicket.objects.select_related(
                'company', 'created_by'
            ),
            pk=self.kwargs['pk']
        )
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        ticket = context['ticket']
        
        # Get responses
        context['responses'] = ticket.responses.select_related('author').order_by('created_at')
        
        # Get available agents for assignment
        context['available_agents'] = SupportTeam.objects.filter(
            is_available=True
        ).select_related('user')
        
        # Get satisfaction survey if resolved
        context['satisfaction_survey'] = getattr(ticket, 'satisfaction_survey', None)
        
        return context


@login_required
def assign_ticket(request, ticket_id):
    """Assign ticket to support agent"""
    if not _is_superadmin(request.user):
        return render(request, 'ems/unauthorized.html')
    
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)
    
    if request.method == 'POST':
        agent_id = request.POST.get('agent_id')
        
        if agent_id:
            try:
                agent = SupportTeam.objects.get(user_id=agent_id)
                ticket.assigned_to = agent.user
                ticket.status = 'IN_PROGRESS'
                ticket.last_response_at = timezone.now()
                ticket.save()
                
                # Create internal response
                TicketResponse.objects.create(
                    ticket=ticket,
                    author=request.user,
                    response_type='INTERNAL',
                    message=f"Ticket assigned to {agent.user.get_full_name()} by {request.user.get_full_name()}"
                )
                
                messages.success(request, f'Ticket assigned to {agent.user.get_full_name()}')
            except SupportTeam.DoesNotExist:
                messages.error(request, 'Invalid agent selected')
        
        return redirect('support:superadmin_ticket_detail', pk=ticket_id)


@login_required
def update_ticket_status(request, ticket_id):
    """Update ticket status"""
    if not _is_superadmin(request.user):
        return render(request, 'ems/unauthorized.html')
    
    ticket = get_object_or_404(SupportTicket, pk=ticket_id)
    
    if request.method == 'POST':
        new_status = request.POST.get('status')
        resolution_note = request.POST.get('resolution_note', '')
        
        if new_status in dict(SupportTicket.Status.choices):
            old_status = ticket.status
            ticket.status = new_status
            ticket.last_response_at = timezone.now()
            
            if new_status == 'RESOLVED' and resolution_note:
                # Create resolution response
                TicketResponse.objects.create(
                    ticket=ticket,
                    author=request.user,
                    response_type='CUSTOMER',
                    message=f"Ticket resolved: {resolution_note}"
                )
                
                # Update agent stats
                if ticket.assigned_to:
                    try:
                        agent_profile = ticket.assigned_to.support_profile
                        agent_profile.tickets_resolved += 1
                        agent_profile.save()
                    except SupportTeam.DoesNotExist:
                        pass
            
            ticket.save()
            messages.success(request, f'Ticket status updated to {new_status}')
        else:
            messages.error(request, 'Invalid status')
    
    return redirect('support:superadmin_ticket_detail', pk=ticket_id)


class SupportTeamListView(SuperAdminRequiredMixin, ListView):
    """List support team members"""
    model = SupportTeam
    template_name = 'blu_support/superadmin_team.html'
    context_object_name = 'team_members'
    
    def get_queryset(self):
        return SupportTeam.objects.select_related('user').annotate(
            current_workload=Count('user__created_support_tickets', 
                               filter=Q(user__created_support_tickets__status__in=['OPEN', 'IN_PROGRESS']))
        ).order_by('-tickets_resolved')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate totals for team overview
        total_resolved = sum(member.tickets_resolved for member in context['team_members'])
        avg_performance = total_resolved / len(context['team_members']) if context['team_members'] else 0
        
        context['total_resolved'] = total_resolved
        context['avg_performance'] = avg_performance
        
        # Team statistics
        context['team_stats'] = SupportTeam.objects.aggregate(
            total_members=Count('id'),
            available_members=Count('id', filter=Q(is_available=True)),
            avg_satisfaction=Avg('satisfaction_score')
        )
        
        # Categories for specialties
        context['categories'] = SupportCategory.objects.all()
        
        return context


class SupportCategoryListView(SuperAdminRequiredMixin, ListView):
    """List support categories"""
    model = SupportCategory
    template_name = 'blu_support/superadmin_categories.html'
    context_object_name = 'categories'
    
    def get_queryset(self):
        # Count tickets by category name since SupportTicket.category is a CharField
        from django.db.models import Case, When, Value, IntegerField
        
        categories = list(SupportCategory.objects.all())
        category_ticket_counts = {}
        
        # Get ticket counts for each category name
        ticket_counts_by_category = SupportTicket.objects.values('category').annotate(
            count=Count('id')
        )
        
        # Create a mapping of category name to ticket count
        for item in ticket_counts_by_category:
            category_ticket_counts[item['category']] = item['count']
        
        # Annotate each category with its ticket count
        annotated_categories = []
        total_tickets = 0
        
        for category in categories:
            ticket_count = category_ticket_counts.get(category.name, 0)
            category.ticket_count = ticket_count
            total_tickets += ticket_count
            annotated_categories.append(category)
        
        return annotated_categories
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Calculate total tickets across all categories
        total_tickets = sum(category.ticket_count for category in context['categories'])
        context['total_tickets'] = total_tickets
        
        # Find most popular category
        most_popular = None
        if context['categories']:
            most_popular = max(context['categories'], key=lambda x: x.ticket_count)
        context['most_popular'] = most_popular
        
        return context


@login_required
def support_analytics(request):
    """Support analytics dashboard"""
    if not _is_superadmin(request.user):
        return render(request, 'ems/unauthorized.html')
    
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)
    
    # Ticket trends (last 30 days)
    ticket_trends = []
    for i in range(30):
        date_point = today - timedelta(days=i)
        daily_stats = SupportTicket.objects.filter(
            created_at__date=date_point
        ).aggregate(
            total=Count('id'),
            resolved=Count('id', filter=Q(status='RESOLVED'))
        )
        ticket_trends.append({
            'date': date_point.strftime('%Y-%m-%d'),
            'created': daily_stats['total'],
            'resolved': daily_stats['resolved']
        })
    
    # Priority distribution
    priority_stats = SupportTicket.objects.values('priority').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Category distribution
    category_stats = SupportTicket.objects.values('category').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Response time analysis
    response_times = SupportTicket.objects.filter(
        created_at__gte=last_30_days
    ).annotate(
        response_time=F('last_response_at') - F('created_at')
    ).aggregate(
        avg_response=Avg('response_time'),
        min_response=Min('response_time'),
        max_response=Max('response_time')
    )
    
    # Team performance
    team_performance = SupportTeam.objects.select_related('user').annotate(
        tickets_handled=Count('user__created_support_tickets'),
        resolved_tickets=Count('user__created_support_tickets', 
                           filter=Q(user__created_support_tickets__status='RESOLVED'))
    ).order_by('-resolved_tickets')
    
    # Calculate totals for analytics
    total_created = sum(trend['created'] for trend in ticket_trends)
    total_resolved = sum(trend['resolved'] for trend in ticket_trends)
    
    # Calculate resolution rate
    resolution_rate = 0
    if total_created > 0:
        resolution_rate = (total_resolved * 100) / total_created
    
    # Calculate priority stats total
    priority_total = sum(stat['count'] for stat in priority_stats)
    
    # Calculate chart heights for ticket trends
    max_created = max(trend['created'] for trend in ticket_trends) if ticket_trends else 1
    
    # Add height percentages to ticket trends
    for trend in ticket_trends:
        trend['height_percent'] = (trend['created'] * 100) / max_created if max_created > 0 else 0
    
    # Add percentage to priority stats
    for stat in priority_stats:
        stat['percentage'] = (stat['count'] * 100) / priority_total if priority_total > 0 else 0
    
    context = {
        'ticket_trends': ticket_trends,
        'priority_stats': priority_stats,
        'category_stats': category_stats,
        'response_times': response_times,
        'team_performance': team_performance,
        'total_created': total_created,
        'total_resolved': total_resolved,
        'resolution_rate': resolution_rate,
        'priority_total': priority_total,
        'max_created': max_created,
    }
    
    return render(request, 'blu_support/support_analytics.html', context)
