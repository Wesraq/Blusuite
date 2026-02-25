from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.db.models import Q, Count
from django.utils import timezone
from datetime import date, timedelta
import csv

from .models import EmployeeContract, ContractAmendment, ContractRenewal, ContractTemplate
from blu_staff.apps.accounts.models import Company, User


@login_required
def contracts_list(request):
    """List all employee contracts for HR/Admin"""
    user = request.user
    
    # Check permissions - Allow EMPLOYER_ADMIN, ADMINISTRATOR, or HR role
    is_hr = hasattr(user, 'employee_profile') and user.employee_profile.employee_role == 'HR'
    if user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] and not is_hr:
        messages.error(request, 'You do not have permission to access contracts.')
        return redirect('employee_dashboard')
    
    # Get company
    company = getattr(user, 'company', None) or getattr(getattr(user, 'employer_profile', None), 'company', None)
    if not company:
        messages.error(request, 'Company not found.')
        return redirect('hr_dashboard')
    
    # Get all contracts for the company
    contracts = EmployeeContract.objects.filter(company=company).select_related('employee', 'employee__employee_profile')
    
    # Filters
    status_filter = request.GET.get('status', '')
    if status_filter:
        contracts = contracts.filter(status=status_filter)
    else:
        # By default, show only ACTIVE contracts (hide EXPIRED and RENEWED to avoid duplicates)
        # This ensures only one entry per employee in the main list
        contracts = contracts.filter(status='ACTIVE')
    
    contract_type_filter = request.GET.get('contract_type', '')
    if contract_type_filter:
        contracts = contracts.filter(contract_type=contract_type_filter)
    
    search_query = request.GET.get('search', '').strip()
    if search_query:
        contracts = contracts.filter(
            Q(employee__first_name__icontains=search_query) |
            Q(employee__last_name__icontains=search_query) |
            Q(employee__email__icontains=search_query) |
            Q(contract_number__icontains=search_query) |
            Q(job_title__icontains=search_query)
        )
    
    # Statistics
    total_contracts = contracts.count()
    active_contracts = contracts.filter(status=EmployeeContract.ContractStatus.ACTIVE).count()
    expiring_soon = sum(1 for c in contracts if c.is_expiring_soon)
    expired_contracts = contracts.filter(status=EmployeeContract.ContractStatus.EXPIRED).count()
    
    # CSV Export
    if request.GET.get('format') == 'csv':
        filename = f"contracts_{date.today().strftime('%Y%m%d')}.csv"
        response = HttpResponse(content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        response.write('\ufeff')
        writer = csv.writer(response)
        
        writer.writerow(['Contract Number', 'Employee', 'Email', 'Job Title', 'Contract Type', 'Status', 'Start Date', 'End Date', 'Salary', 'Currency'])
        
        for contract in contracts:
            writer.writerow([
                contract.contract_number,
                contract.employee.get_full_name(),
                contract.employee.email,
                contract.job_title,
                contract.get_contract_type_display(),
                contract.get_status_display(),
                contract.start_date.strftime('%Y-%m-%d'),
                contract.end_date.strftime('%Y-%m-%d') if contract.end_date else 'N/A',
                contract.salary or 'N/A',
                contract.currency,
            ])
        
        return response
    
    context = {
        'contracts': contracts.order_by('-created_at'),
        'total_contracts': total_contracts,
        'active_contracts': active_contracts,
        'expiring_soon': expiring_soon,
        'expired_contracts': expired_contracts,
        'status_filter': status_filter,
        'contract_type_filter': contract_type_filter,
        'search_query': search_query,
        'status_choices': EmployeeContract.ContractStatus.choices,
        'contract_type_choices': EmployeeContract.ContractType.choices,
    }
    
    return render(request, 'contracts/contracts_list.html', context)


@login_required
def contract_detail(request, contract_id):
    """View contract details"""
    user = request.user
    
    # Check permissions - Allow EMPLOYER_ADMIN, ADMINISTRATOR, or HR role
    is_hr = hasattr(user, 'employee_profile') and user.employee_profile.employee_role == 'HR'
    if user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] and not is_hr:
        messages.error(request, 'You do not have permission to view contracts.')
        return redirect('employee_dashboard')
    
    contract = get_object_or_404(EmployeeContract, id=contract_id)
    
    # Get amendments and renewals
    amendments = contract.amendments.all().order_by('-amendment_date')
    renewals = contract.renewal_requests.all().order_by('-requested_at')
    
    # Get all contracts for this employee (contract history)
    contract_history = EmployeeContract.objects.filter(
        employee=contract.employee,
        company=contract.company
    ).exclude(id=contract.id).order_by('-created_at')
    
    context = {
        'contract': contract,
        'amendments': amendments,
        'renewals': renewals,
        'contract_history': contract_history,
    }
    
    return render(request, 'contracts/contract_detail.html', context)


@login_required
def contract_create(request):
    """Create new employee contract"""
    user = request.user
    
    # Check permissions - Allow EMPLOYER_ADMIN, ADMINISTRATOR, or HR role
    is_hr = hasattr(user, 'employee_profile') and user.employee_profile.employee_role == 'HR'
    if user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] and not is_hr:
        messages.error(request, 'You do not have permission to create contracts.')
        return redirect('employee_dashboard')
    
    # Get company
    company = getattr(user, 'company', None) or getattr(getattr(user, 'employer_profile', None), 'company', None)
    if not company:
        messages.error(request, 'Company not found.')
        return redirect('hr_dashboard')
    
    if request.method == 'POST':
        try:
            # Get employee
            employee_id = request.POST.get('employee_id')
            employee = get_object_or_404(User, id=employee_id, company=company)
            
            # Create contract
            contract = EmployeeContract(
                employee=employee,
                company=company,
                contract_type=request.POST.get('contract_type'),
                status=request.POST.get('status', EmployeeContract.ContractStatus.DRAFT),
                job_title=request.POST.get('job_title'),
                department=request.POST.get('department', ''),
                start_date=request.POST.get('start_date'),
                end_date=request.POST.get('end_date') or None,
                salary=request.POST.get('salary') or None,
                currency=request.POST.get('currency', 'ZMW'),
                salary_frequency=request.POST.get('salary_frequency', 'MONTHLY'),
                working_hours_per_week=request.POST.get('working_hours_per_week', 40.00),
                probation_period_months=request.POST.get('probation_period_months') or None,
                notice_period_days=request.POST.get('notice_period_days', 30),
                renewal_notice_period_days=request.POST.get('renewal_notice_period_days', 30),
                auto_renew=request.POST.get('auto_renew') == 'on',
                terms_and_conditions=request.POST.get('terms_and_conditions', ''),
                special_clauses=request.POST.get('special_clauses', ''),
                created_by=user,
            )
            
            # Handle file uploads
            if 'contract_document' in request.FILES:
                contract.contract_document = request.FILES['contract_document']
            
            contract.save()
            
            messages.success(request, f'Contract {contract.contract_number} created successfully.')
            return redirect('contract_detail', contract_id=contract.id)
            
        except Exception as e:
            messages.error(request, f'Error creating contract: {str(e)}')
    
    # Get employees for dropdown
    employees = User.objects.filter(company=company, role='EMPLOYEE').order_by('first_name', 'last_name')
    
    # Get templates
    templates = ContractTemplate.objects.filter(company=company, is_active=True)
    
    context = {
        'employees': employees,
        'templates': templates,
        'contract_type_choices': EmployeeContract.ContractType.choices,
        'status_choices': EmployeeContract.ContractStatus.choices,
        'salary_frequency_choices': [
            ('HOURLY', 'Hourly'),
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('ANNUALLY', 'Annually'),
        ],
    }
    
    return render(request, 'contracts/contract_create.html', context)


@login_required
def contract_edit(request, contract_id):
    """Edit existing contract"""
    user = request.user
    
    # Check permissions - Allow EMPLOYER_ADMIN, ADMINISTRATOR, or HR role
    is_hr = hasattr(user, 'employee_profile') and user.employee_profile.employee_role == 'HR'
    if user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] and not is_hr:
        messages.error(request, 'You do not have permission to edit contracts.')
        return redirect('employee_dashboard')
    
    contract = get_object_or_404(EmployeeContract, id=contract_id)
    
    if request.method == 'POST':
        try:
            # Store previous values for amendment tracking
            previous_values = {
                'job_title': contract.job_title,
                'salary': str(contract.salary) if contract.salary else None,
                'end_date': str(contract.end_date) if contract.end_date else None,
            }
            
            # Update contract
            contract.contract_type = request.POST.get('contract_type')
            contract.status = request.POST.get('status')
            contract.job_title = request.POST.get('job_title')
            contract.department = request.POST.get('department', '')
            contract.start_date = request.POST.get('start_date')
            contract.end_date = request.POST.get('end_date') or None
            contract.salary = request.POST.get('salary') or None
            contract.currency = request.POST.get('currency', 'ZMW')
            contract.salary_frequency = request.POST.get('salary_frequency', 'MONTHLY')
            contract.working_hours_per_week = request.POST.get('working_hours_per_week', 40.00)
            contract.probation_period_months = request.POST.get('probation_period_months') or None
            contract.notice_period_days = request.POST.get('notice_period_days', 30)
            contract.renewal_notice_period_days = request.POST.get('renewal_notice_period_days', 30)
            contract.auto_renew = request.POST.get('auto_renew') == 'on'
            contract.terms_and_conditions = request.POST.get('terms_and_conditions', '')
            contract.special_clauses = request.POST.get('special_clauses', '')
            
            # Handle file uploads
            if 'contract_document' in request.FILES:
                contract.contract_document = request.FILES['contract_document']
            
            if 'signed_contract_document' in request.FILES:
                contract.signed_contract_document = request.FILES['signed_contract_document']
            
            contract.save()
            
            # Sync contract data to employee profile if contract is ACTIVE
            if contract.status == 'ACTIVE' and hasattr(contract.employee, 'employee_profile') and contract.employee.employee_profile:
                profile = contract.employee.employee_profile
                profile.job_title = contract.job_title
                profile.department = contract.department
                profile.salary = contract.salary
                profile.contract_start_date = contract.start_date
                profile.contract_end_date = contract.end_date
                profile.employment_type = 'CONTRACT' if contract.contract_type == 'FIXED_TERM' else 'PERMANENT'
                profile.save()
            
            # Create amendment record if significant changes
            new_values = {
                'job_title': contract.job_title,
                'salary': str(contract.salary) if contract.salary else None,
                'end_date': str(contract.end_date) if contract.end_date else None,
            }
            
            if previous_values != new_values:
                amendment_count = contract.amendments.count() + 1
                ContractAmendment.objects.create(
                    contract=contract,
                    amendment_number=f"{contract.contract_number}-AMD-{amendment_count:03d}",
                    amendment_date=date.today(),
                    effective_date=date.today(),
                    description=request.POST.get('amendment_description', 'Contract updated'),
                    previous_values=previous_values,
                    new_values=new_values,
                    created_by=user,
                )
            
            messages.success(request, 'Contract updated successfully. Employee profile has been synced with the new contract details.')
            return redirect('contract_detail', contract_id=contract.id)
            
        except Exception as e:
            messages.error(request, f'Error updating contract: {str(e)}')
    
    context = {
        'contract': contract,
        'contract_type_choices': EmployeeContract.ContractType.choices,
        'status_choices': EmployeeContract.ContractStatus.choices,
        'salary_frequency_choices': [
            ('HOURLY', 'Hourly'),
            ('DAILY', 'Daily'),
            ('WEEKLY', 'Weekly'),
            ('MONTHLY', 'Monthly'),
            ('ANNUALLY', 'Annually'),
        ],
    }
    
    return render(request, 'contracts/contract_edit.html', context)


@login_required
def contract_renew(request, contract_id):
    """Initiate contract renewal"""
    user = request.user
    
    # Check permissions - Allow EMPLOYER_ADMIN, ADMINISTRATOR, or HR role
    is_hr = hasattr(user, 'employee_profile') and user.employee_profile.employee_role == 'HR'
    if user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] and not is_hr:
        messages.error(request, 'You do not have permission to renew contracts.')
        return redirect('employee_dashboard')
    
    contract = get_object_or_404(EmployeeContract, id=contract_id)
    
    if request.method == 'POST':
        print("=" * 80)
        print(f"CONTRACT RENEWAL POST REQUEST RECEIVED")
        print(f"Contract ID: {contract_id}")
        print(f"User: {user.username}")
        print(f"POST Data: {dict(request.POST)}")
        print("=" * 80)
        
        try:
            # Get company
            company = contract.company
            
            # Get the action from the button clicked
            action = request.POST.get('action', 'submit_for_approval')
            
            print(f">>> ACTION DETECTED: '{action}'")
            
            # Debug logging
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Renewal action received: '{action}' for contract {contract_id}")
            logger.info(f"POST data: {dict(request.POST)}")
            
            # Check which button was clicked
            if action == 'renew_now':
                # Direct renewal - no approval needed
                from django.utils import timezone
                from django.core.mail import send_mail
                from django.conf import settings
                import logging
                
                logger = logging.getLogger(__name__)
                logger.info(f"Direct renewal initiated for contract {contract_id} by {user.username}")
                
                # Check if contract is already renewed
                if contract.status == 'RENEWED':
                    messages.warning(request, 'This contract has already been renewed. Please view the new contract instead.')
                    # Find the new contract
                    newer_contracts = EmployeeContract.objects.filter(
                        employee=contract.employee,
                        status='ACTIVE',
                        created_at__gt=contract.created_at
                    ).order_by('-created_at').first()
                    
                    if newer_contracts:
                        return redirect('contracts:contract_detail', contract_id=newer_contracts.id)
                    else:
                        return redirect('contracts:contracts_list')
                
                # Mark any other active contracts for this employee as expired
                EmployeeContract.objects.filter(
                    employee=contract.employee,
                    status='ACTIVE'
                ).exclude(id=contract.id).update(status='EXPIRED')
                
                # Generate new contract number
                year = timezone.now().year
                existing_count = EmployeeContract.objects.filter(
                    company=company,
                    created_at__year=year
                ).count()
                new_contract_number = f"CONT-{year}-{existing_count + 1:04d}"
                
                # Get proposed values
                proposed_start_date = request.POST.get('proposed_start_date')
                proposed_end_date = request.POST.get('proposed_end_date') or None
                proposed_salary = request.POST.get('proposed_salary') or None
                proposed_job_title = request.POST.get('proposed_job_title', '').strip()
                proposed_terms = request.POST.get('proposed_terms', '').strip()
                
                logger.info(f"Creating new contract with number: {new_contract_number}")
                
                # Create new contract directly
                print(f">>> Creating new contract with:")
                print(f"    Employee: {contract.employee.get_full_name()}")
                print(f"    Contract Number: {new_contract_number}")
                print(f"    Start Date: {proposed_start_date}")
                print(f"    End Date: {proposed_end_date}")
                print(f"    Salary: {proposed_salary or contract.salary}")
                
                new_contract = EmployeeContract.objects.create(
                    employee=contract.employee,
                    company=company,
                    contract_number=new_contract_number,
                    contract_type=contract.contract_type,
                    job_title=proposed_job_title if proposed_job_title else contract.job_title,
                    department=contract.department,
                    start_date=proposed_start_date,
                    end_date=proposed_end_date,
                    salary=proposed_salary if proposed_salary else contract.salary,
                    currency=contract.currency,
                    salary_frequency=contract.salary_frequency,
                    working_hours_per_week=contract.working_hours_per_week,
                    probation_period_months=contract.probation_period_months,
                    notice_period_days=contract.notice_period_days,
                    terms_and_conditions=proposed_terms if proposed_terms else contract.terms_and_conditions,
                    special_clauses=contract.special_clauses,
                    status='ACTIVE',
                    created_by=user,
                )
                
                print(f">>> NEW CONTRACT CREATED SUCCESSFULLY!")
                print(f"    ID: {new_contract.id}")
                print(f"    Contract Number: {new_contract.contract_number}")
                print(f"    Status: {new_contract.status}")
                
                logger.info(f"New contract created: {new_contract.id} - {new_contract.contract_number}")
                
                # Update old contract status
                contract.status = 'RENEWED'
                contract.save()
                logger.info(f"Old contract {contract.id} marked as RENEWED")
                
                # Sync contract data to employee profile
                if hasattr(contract.employee, 'employee_profile') and contract.employee.employee_profile:
                    profile = contract.employee.employee_profile
                    profile.job_title = new_contract.job_title
                    profile.department = new_contract.department
                    profile.salary = new_contract.salary
                    profile.contract_start_date = new_contract.start_date
                    profile.contract_end_date = new_contract.end_date
                    profile.employment_type = 'CONTRACT' if new_contract.contract_type == 'FIXED_TERM' else 'PERMANENT'
                    profile.save()
                    print(f">>> EMPLOYEE PROFILE UPDATED!")
                    print(f"    Job Title: {profile.job_title}")
                    print(f"    Department: {profile.department}")
                    print(f"    Salary: {profile.salary}")
                    print(f"    Contract Period: {profile.contract_start_date} to {profile.contract_end_date}")
                    logger.info(f"Employee profile synced with new contract data for {contract.employee.id}")
                
                # Create in-app notification for employee
                from blu_staff.apps.notifications.models import Notification
                print(f">>> Attempting to create in-app notification for employee")
                print(f"    Employee: {contract.employee.get_full_name()}")
                print(f"    Employee ID: {contract.employee.id}")
                
                # contract.employee is already a User object
                try:
                    notification = Notification.objects.create(
                        recipient=contract.employee,
                        sender=user,
                        title='Your Contract Has Been Renewed',
                        message=f'Your employment contract has been renewed. New contract number: {new_contract.contract_number}. Start date: {new_contract.start_date}',
                        notification_type='SUCCESS',
                        category='contract',
                        link=f'/contracts/{new_contract.id}/',
                    )
                    print(f">>> IN-APP NOTIFICATION CREATED!")
                    print(f"    Notification ID: {notification.id}")
                    print(f"    Recipient: {notification.recipient.get_full_name()}")
                    logger.info(f"In-app notification created for employee {contract.employee.id}")
                except Exception as notif_error:
                    print(f">>> ERROR creating notification: {str(notif_error)}")
                    import traceback
                    print(traceback.format_exc())
                    logger.error(f"Error creating in-app notification: {str(notif_error)}")
                
                # Send notification to employee
                employee_email = contract.employee.email
                if employee_email:
                    try:
                        subject = 'Your Contract Has Been Renewed'
                        message = f"""Hello {contract.employee.get_full_name()},

Your employment contract has been renewed.

New Contract Details:
- Contract Number: {new_contract.contract_number}
- Start Date: {new_contract.start_date}
- End Date: {new_contract.end_date or 'Permanent'}
- Job Title: {new_contract.job_title}
- Salary: {new_contract.currency} {new_contract.salary}

Please log in to the system to view your new contract details.

Best regards,
{company.name}
"""
                        send_mail(
                            subject, 
                            message, 
                            settings.DEFAULT_FROM_EMAIL, 
                            [employee_email],
                            fail_silently=False
                        )
                        logger.info(f"Renewal notification sent to {employee_email}")
                        messages.info(request, f'Email notification sent to {contract.employee.get_full_name()}')
                    except Exception as e:
                        logger.error(f"Error sending renewal notification: {str(e)}")
                        messages.warning(request, f'Contract created but email notification failed: {str(e)}')
                else:
                    logger.warning(f"No email address for employee {contract.employee.id}")
                    messages.warning(request, 'Contract created but employee has no email address.')
                
                print(f">>> RENEWAL COMPLETE - Redirecting to new contract")
                print(f"    New Contract ID: {new_contract.id}")
                print(f"    Redirect URL: /contracts/{new_contract.id}/")
                print("=" * 80)
                
                messages.success(request, f'Contract renewed successfully! New contract {new_contract.contract_number} created.')
                messages.info(request, f'Viewing new contract: {new_contract.contract_number}')
                
                from django.shortcuts import redirect
                return redirect('contracts:contract_detail', contract_id=new_contract.id)
            
            elif action == 'submit_for_approval':
                # Standard approval workflow
                renewal = ContractRenewal.objects.create(
                    original_contract=contract,
                    proposed_start_date=request.POST.get('proposed_start_date'),
                    proposed_end_date=request.POST.get('proposed_end_date') or None,
                    proposed_salary=request.POST.get('proposed_salary') or None,
                    proposed_job_title=request.POST.get('proposed_job_title', ''),
                    proposed_terms=request.POST.get('proposed_terms', ''),
                    renewal_notes=request.POST.get('renewal_notes', ''),
                    requested_by=user,
                )
                
                # Send notification to admins
                send_renewal_submitted_notification(renewal)
                
                messages.success(request, 'Renewal request submitted successfully. Admin will review and approve.')
                return redirect('contracts:contract_detail', contract_id=contract.id)
            
            else:
                # Unknown action
                logger.warning(f"Unknown renewal action: '{action}'")
                messages.error(request, f'Invalid action: {action}. Please try again.')
                return redirect('contracts:contract_renew', contract_id=contract_id)
            
        except Exception as e:
            import traceback
            logger.error(f"Error in contract renewal: {str(e)}\n{traceback.format_exc()}")
            messages.error(request, f'Error creating renewal: {str(e)}')
    
    # Calculate suggested dates
    suggested_start = contract.end_date + timedelta(days=1) if contract.end_date else date.today()
    suggested_end = suggested_start + timedelta(days=365) if contract.end_date else None
    
    # Get approval requirement (default to True if not set)
    require_approval = getattr(contract.company, 'require_renewal_approval', True)
    
    context = {
        'contract': contract,
        'suggested_start': suggested_start,
        'suggested_end': suggested_end,
        'require_approval': require_approval,
    }
    
    return render(request, 'contracts/contract_renew.html', context)


@login_required
def expiring_contracts(request):
    """View contracts expiring soon"""
    user = request.user
    
    # Check permissions - Allow EMPLOYER_ADMIN, ADMINISTRATOR, or HR role
    is_hr = hasattr(user, 'employee_profile') and user.employee_profile.employee_role == 'HR'
    if user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] and not is_hr:
        messages.error(request, 'You do not have permission to access contracts.')
        return redirect('employee_dashboard')
    
    # Get company
    company = getattr(user, 'company', None) or getattr(getattr(user, 'employer_profile', None), 'company', None)
    if not company:
        messages.error(request, 'Company not found.')
        return redirect('hr_dashboard')
    
    # Get expiring contracts (next 60 days)
    today = date.today()
    sixty_days_from_now = today + timedelta(days=60)
    
    expiring = EmployeeContract.objects.filter(
        company=company,
        status=EmployeeContract.ContractStatus.ACTIVE,
        end_date__isnull=False,
        end_date__gte=today,
        end_date__lte=sixty_days_from_now
    ).select_related('employee', 'employee__employee_profile').order_by('end_date')
    
    context = {
        'expiring_contracts': expiring,
        'today': today,
    }
    
    return render(request, 'contracts/expiring_contracts.html', context)


@login_required
def renewal_requests(request):
    """Dashboard showing all contract renewal requests"""
    user = request.user
    
    # Check permissions - Allow EMPLOYER_ADMIN, ADMINISTRATOR, or HR role
    is_hr = hasattr(user, 'employee_profile') and user.employee_profile.employee_role == 'HR'
    if user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'] and not is_hr:
        messages.error(request, 'You do not have permission to access renewal requests.')
        return redirect('employee_dashboard')
    
    # Get company
    company = getattr(user, 'company', None) or getattr(getattr(user, 'employer_profile', None), 'company', None)
    if not company:
        messages.error(request, 'Company not found.')
        return redirect('hr_dashboard')
    
    # Get filter from query params
    status_filter = request.GET.get('status', 'PENDING')
    
    # Get renewal requests
    renewals = ContractRenewal.objects.filter(
        original_contract__company=company
    ).select_related(
        'original_contract', 
        'original_contract__employee',
        'requested_by',
        'reviewed_by'
    ).order_by('-requested_at')
    
    # Apply status filter
    if status_filter and status_filter != 'ALL':
        renewals = renewals.filter(status=status_filter)
    
    # Separate pending renewals for admins
    pending_renewals = renewals.filter(status='PENDING')
    
    context = {
        'renewals': renewals,
        'pending_renewals': pending_renewals,
        'status_filter': status_filter,
        'is_admin': user.role in ['EMPLOYER_ADMIN', 'ADMINISTRATOR'],
    }
    
    return render(request, 'contracts/renewal_requests.html', context)


@login_required
def approve_renewal(request, renewal_id):
    """Approve a contract renewal request"""
    user = request.user
    
    # Only EMPLOYER_ADMIN and ADMINISTRATOR can approve
    if user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        messages.error(request, 'You do not have permission to approve renewals.')
        return redirect('contracts:renewal_requests')
    
    renewal = get_object_or_404(ContractRenewal, id=renewal_id)
    
    if renewal.status != 'PENDING':
        messages.warning(request, 'This renewal request has already been processed.')
        return redirect('contracts:renewal_requests')
    
    try:
        from django.utils import timezone
        
        # Update renewal status
        renewal.status = 'APPROVED'
        renewal.reviewed_by = user
        renewal.reviewed_at = timezone.now()
        renewal.save()
        
        # Create new contract
        old_contract = renewal.original_contract
        
        # Generate new contract number
        year = timezone.now().year
        existing_count = EmployeeContract.objects.filter(
            company=old_contract.company,
            created_at__year=year
        ).count()
        new_contract_number = f"CONT-{year}-{existing_count + 1:04d}"
        
        # Create new contract
        new_contract = EmployeeContract.objects.create(
            employee=old_contract.employee,
            company=old_contract.company,
            contract_number=new_contract_number,
            contract_type=old_contract.contract_type,
            job_title=renewal.proposed_job_title if renewal.proposed_job_title else old_contract.job_title,
            department=old_contract.department,
            start_date=renewal.proposed_start_date,
            end_date=renewal.proposed_end_date,
            salary=renewal.proposed_salary if renewal.proposed_salary else old_contract.salary,
            currency=old_contract.currency,
            salary_frequency=old_contract.salary_frequency,
            working_hours_per_week=old_contract.working_hours_per_week,
            probation_period_months=old_contract.probation_period_months,
            notice_period_days=old_contract.notice_period_days,
            terms_and_conditions=renewal.proposed_terms if renewal.proposed_terms else old_contract.terms_and_conditions,
            special_clauses=old_contract.special_clauses,
            status='ACTIVE',
            created_by=user,
        )
        
        # Link new contract to renewal
        renewal.new_contract = new_contract
        renewal.status = 'COMPLETED'
        renewal.save()
        
        # Update old contract status
        old_contract.status = 'RENEWED'
        old_contract.save()
        
        # Sync contract data to employee profile
        if hasattr(old_contract.employee, 'employee_profile') and old_contract.employee.employee_profile:
            profile = old_contract.employee.employee_profile
            profile.job_title = new_contract.job_title
            profile.department = new_contract.department
            profile.salary = new_contract.salary
            profile.contract_start_date = new_contract.start_date
            profile.contract_end_date = new_contract.end_date
            profile.employment_type = 'CONTRACT' if new_contract.contract_type == 'FIXED_TERM' else 'PERMANENT'
            profile.save()
        
        # Send notifications
        send_renewal_approved_notification(renewal, user)
        
        messages.success(request, f'Contract renewal approved! New contract {new_contract.contract_number} created. Employee profile updated.')
        return redirect('contracts:contract_detail', contract_id=new_contract.id)
        
    except Exception as e:
        messages.error(request, f'Error approving renewal: {str(e)}')
        return redirect('contracts:renewal_requests')


@login_required
def reject_renewal(request, renewal_id):
    """Reject a contract renewal request"""
    user = request.user
    
    # Only EMPLOYER_ADMIN and ADMINISTRATOR can reject
    if user.role not in ['EMPLOYER_ADMIN', 'ADMINISTRATOR']:
        messages.error(request, 'You do not have permission to reject renewals.')
        return redirect('contracts:renewal_requests')
    
    renewal = get_object_or_404(ContractRenewal, id=renewal_id)
    
    if renewal.status != 'PENDING':
        messages.warning(request, 'This renewal request has already been processed.')
        return redirect('contracts:renewal_requests')
    
    if request.method == 'POST':
        try:
            from django.utils import timezone
            
            rejection_reason = request.POST.get('rejection_reason', '')
            
            if not rejection_reason:
                messages.error(request, 'Please provide a reason for rejection.')
                return redirect('contracts:renewal_requests')
            
            # Update renewal status
            renewal.status = 'REJECTED'
            renewal.reviewed_by = user
            renewal.reviewed_at = timezone.now()
            renewal.rejection_reason = rejection_reason
            renewal.save()
            
            # Send notifications
            send_renewal_rejected_notification(renewal, user, rejection_reason)
            
            messages.success(request, 'Contract renewal rejected.')
            return redirect('contracts:renewal_requests')
            
        except Exception as e:
            messages.error(request, f'Error rejecting renewal: {str(e)}')
            return redirect('contracts:renewal_requests')
    
    # GET request - show rejection form
    context = {
        'renewal': renewal,
    }
    return render(request, 'contracts/reject_renewal.html', context)


def send_renewal_approved_notification(renewal, approved_by):
    """Send notification when renewal is approved"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from blu_staff.apps.notifications.models import Notification
        
        # Create in-app notification for HR who submitted the request
        if renewal.requested_by:
            Notification.objects.create(
                recipient=renewal.requested_by,
                sender=approved_by,
                title='Contract Renewal Approved',
                message=f'Renewal request for {renewal.original_contract.employee.get_full_name()} has been approved. New contract: {renewal.new_contract.contract_number if renewal.new_contract else "Pending"}',
                notification_type='SUCCESS',
                category='contract_renewal',
                link=f'/contracts/{renewal.new_contract.id}/' if renewal.new_contract else '/contracts/renewals/',
            )
        
        # Create in-app notification for the employee
        if renewal.original_contract.employee.user:
            Notification.objects.create(
                recipient=renewal.original_contract.employee.user,
                sender=approved_by,
                title='Your Contract Has Been Renewed',
                message=f'Your employment contract has been renewed. New contract number: {renewal.new_contract.contract_number if renewal.new_contract else "Pending"}',
                notification_type='SUCCESS',
                category='contract',
                link=f'/contracts/{renewal.new_contract.id}/' if renewal.new_contract else '/contracts/',
            )
        
        # Notify HR who submitted the request via email
        if renewal.requested_by and renewal.requested_by.email:
            subject = f'Contract Renewal Approved - {renewal.original_contract.employee.get_full_name()}'
            message = f"""
Your contract renewal request has been approved.

Employee: {renewal.original_contract.employee.get_full_name()}
Original Contract: {renewal.original_contract.contract_number}
New Contract: {renewal.new_contract.contract_number if renewal.new_contract else 'Pending'}

Approved by: {approved_by.get_full_name()}
Date: {renewal.reviewed_at.strftime('%Y-%m-%d %H:%M')}

The new contract has been created and is now active.

Best regards,
{renewal.original_contract.company.name}
            """
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [renewal.requested_by.email], fail_silently=True)
        
        # Notify the employee via email
        if renewal.original_contract.employee.email:
            subject = 'Your Contract Has Been Renewed'
            message = f"""
Hello {renewal.original_contract.employee.get_full_name()},

Your employment contract has been renewed.

New Contract Details:
- Contract Number: {renewal.new_contract.contract_number if renewal.new_contract else 'Pending'}
- Start Date: {renewal.proposed_start_date}
- End Date: {renewal.proposed_end_date or 'Permanent'}
- Job Title: {renewal.proposed_job_title or renewal.original_contract.job_title}

Please contact HR if you have any questions.

Best regards,
{renewal.original_contract.company.name}
            """
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [renewal.original_contract.employee.email], fail_silently=True)
            
    except Exception as e:
        print(f"Error sending renewal approved notification: {str(e)}")


def send_renewal_rejected_notification(renewal, rejected_by, reason):
    """Send notification when renewal is rejected"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from blu_staff.apps.notifications.models import Notification
        
        # Create in-app notification for HR who submitted the request
        if renewal.requested_by:
            Notification.objects.create(
                recipient=renewal.requested_by,
                sender=rejected_by,
                title='Contract Renewal Rejected',
                message=f'Renewal request for {renewal.original_contract.employee.get_full_name()} was rejected. Reason: {reason[:100]}...' if len(reason) > 100 else f'Renewal request for {renewal.original_contract.employee.get_full_name()} was rejected. Reason: {reason}',
                notification_type='WARNING',
                category='contract_renewal',
                link=f'/contracts/renewals/',
            )
        
        # Notify HR who submitted the request via email
        if renewal.requested_by and renewal.requested_by.email:
            subject = f'Contract Renewal Rejected - {renewal.original_contract.employee.get_full_name()}'
            message = f"""
Your contract renewal request has been rejected.

Employee: {renewal.original_contract.employee.get_full_name()}
Contract: {renewal.original_contract.contract_number}

Rejected by: {rejected_by.get_full_name()}
Date: {renewal.reviewed_at.strftime('%Y-%m-%d %H:%M')}

Reason for Rejection:
{reason}

You may submit a new renewal request with adjusted terms.

Best regards,
{renewal.original_contract.company.name}
            """
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [renewal.requested_by.email], fail_silently=True)
            
    except Exception as e:
        print(f"Error sending renewal rejected notification: {str(e)}")


def send_renewal_submitted_notification(renewal):
    """Send notification when HR submits a renewal request"""
    try:
        from django.core.mail import send_mail
        from django.conf import settings
        from blu_staff.apps.notifications.models import Notification
        
        # Get all admins and directors
        admins = User.objects.filter(
            role__in=['EMPLOYER_ADMIN', 'ADMINISTRATOR'],
            company=renewal.original_contract.company
        )
        
        if not admins.exists():
            return
        
        # Create in-app notifications for each admin
        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                sender=renewal.requested_by,
                title='New Contract Renewal Request',
                message=f'{renewal.original_contract.employee.get_full_name()} - {renewal.original_contract.job_title}. Proposed start: {renewal.proposed_start_date}',
                notification_type='INFO',
                category='contract_renewal',
                link=f'/contracts/renewals/',
            )
        
        # Send email notifications
        admin_emails = [admin.email for admin in admins if admin.email]
        
        if admin_emails:
            subject = f'New Contract Renewal Request - {renewal.original_contract.employee.get_full_name()}'
            message = f"""
A new contract renewal request has been submitted and requires your approval.

Employee: {renewal.original_contract.employee.get_full_name()}
Current Contract: {renewal.original_contract.contract_number}
Job Title: {renewal.original_contract.job_title}

Proposed Start Date: {renewal.proposed_start_date}
Proposed End Date: {renewal.proposed_end_date or 'Permanent'}
Proposed Salary: {renewal.proposed_salary or 'No change'}

Submitted by: {renewal.requested_by.get_full_name()}
Date: {renewal.requested_at.strftime('%Y-%m-%d %H:%M')}

Notes: {renewal.renewal_notes or 'None'}

Please log in to review and approve this renewal request.

Best regards,
{renewal.original_contract.company.name}
            """
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, admin_emails, fail_silently=True)
    except Exception as e:
        print(f"Error sending renewal submitted notification: {str(e)}")
