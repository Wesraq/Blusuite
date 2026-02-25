"""
Training and Development utility functions for course management and tracking
"""
from django.utils import timezone
from datetime import timedelta


def enroll_employee_in_training(employee, program, enrollment_date=None, target_completion_date=None, tenant=None):
    """
    Enroll an employee in a training program
    
    Args:
        employee: User object
        program: TrainingProgram object
        enrollment_date: Date of enrollment (defaults to today)
        target_completion_date: Target completion date
        tenant: Tenant object for multi-tenancy
    
    Returns:
        TrainingEnrollment object
    """
    from training.models import TrainingEnrollment
    
    if not enrollment_date:
        enrollment_date = timezone.now().date()
    
    if not target_completion_date and hasattr(program, 'duration_days'):
        target_completion_date = enrollment_date + timedelta(days=program.duration_days)
    
    # Check if already enrolled
    existing = TrainingEnrollment.objects.filter(
        employee=employee,
        program=program,
        status__in=['NOT_STARTED', 'IN_PROGRESS']
    ).exists()
    
    if existing:
        return None, "Already enrolled in this program"
    
    try:
        enrollment = TrainingEnrollment.objects.create(
            employee=employee,
            program=program,
            enrollment_date=enrollment_date,
            target_completion_date=target_completion_date,
            status='NOT_STARTED',
            tenant=tenant
        )
        
        # Send notification
        from notifications.utils import notify_training_enrollment
        notify_training_enrollment(enrollment, tenant=tenant)
        
        return enrollment, "Successfully enrolled"
    except Exception as e:
        return None, f"Enrollment failed: {str(e)}"


def start_training(enrollment):
    """Mark a training enrollment as started"""
    if enrollment.status == 'NOT_STARTED':
        enrollment.status = 'IN_PROGRESS'
        enrollment.start_date = timezone.now().date()
        enrollment.save()
        return True
    return False


def complete_training(enrollment, completion_date=None, score=None, notes=''):
    """Mark a training enrollment as completed"""
    if enrollment.status in ['NOT_STARTED', 'IN_PROGRESS']:
        enrollment.status = 'COMPLETED'
        enrollment.completion_date = completion_date or timezone.now().date()
        enrollment.score = score
        enrollment.notes = notes
        enrollment.save()
        
        # Create certificate if applicable
        if hasattr(enrollment.program, 'issues_certificate') and enrollment.program.issues_certificate:
            create_training_certificate(enrollment)
        
        return True
    return False


def create_training_certificate(enrollment):
    """Create a training certificate for completed training"""
    from training.models import TrainingCertificate
    
    certificate = TrainingCertificate.objects.create(
        enrollment=enrollment,
        employee=enrollment.employee,
        program=enrollment.program,
        issue_date=timezone.now().date(),
        certificate_number=f"CERT-{enrollment.id}-{timezone.now().strftime('%Y%m%d')}",
        tenant=getattr(enrollment, 'tenant', None)
    )
    
    return certificate


def get_employee_training_summary(employee):
    """Get training summary for an employee"""
    from training.models import TrainingEnrollment
    
    enrollments = TrainingEnrollment.objects.filter(employee=employee)
    
    total = enrollments.count()
    completed = enrollments.filter(status='COMPLETED').count()
    in_progress = enrollments.filter(status='IN_PROGRESS').count()
    not_started = enrollments.filter(status='NOT_STARTED').count()
    
    completion_rate = (completed / total * 100) if total > 0 else 0
    
    # Get certificates
    from training.models import TrainingCertificate
    certificates = TrainingCertificate.objects.filter(employee=employee).count()
    
    return {
        'total_enrollments': total,
        'completed': completed,
        'in_progress': in_progress,
        'not_started': not_started,
        'completion_rate': round(completion_rate, 2),
        'certificates_earned': certificates
    }


def get_training_programs_for_employee(employee, company):
    """Get available training programs for an employee"""
    from training.models import TrainingProgram, TrainingEnrollment
    
    all_programs = TrainingProgram.objects.filter(
        tenant=getattr(employee, 'tenant', None),
        is_active=True
    )
    
    # Get programs employee is already enrolled in
    enrolled_program_ids = TrainingEnrollment.objects.filter(
        employee=employee,
        status__in=['NOT_STARTED', 'IN_PROGRESS']
    ).values_list('program_id', flat=True)
    
    available_programs = []
    
    for program in all_programs:
        is_enrolled = program.id in enrolled_program_ids
        
        available_programs.append({
            'program': program,
            'is_enrolled': is_enrolled,
            'is_mandatory': getattr(program, 'is_mandatory', False)
        })
    
    return available_programs


def get_overdue_trainings(company, tenant=None):
    """Get overdue training enrollments"""
    from training.models import TrainingEnrollment
    
    overdue = TrainingEnrollment.objects.filter(
        employee__company=company,
        status__in=['NOT_STARTED', 'IN_PROGRESS'],
        target_completion_date__lt=timezone.now().date()
    ).select_related('employee', 'program')
    
    if tenant:
        overdue = overdue.filter(tenant=tenant)
    
    return overdue


def get_upcoming_training_deadlines(company, days=30, tenant=None):
    """Get training enrollments with upcoming deadlines"""
    from training.models import TrainingEnrollment
    
    end_date = timezone.now().date() + timedelta(days=days)
    
    upcoming = TrainingEnrollment.objects.filter(
        employee__company=company,
        status__in=['NOT_STARTED', 'IN_PROGRESS'],
        target_completion_date__range=[timezone.now().date(), end_date]
    ).select_related('employee', 'program').order_by('target_completion_date')
    
    if tenant:
        upcoming = upcoming.filter(tenant=tenant)
    
    return upcoming


def bulk_enroll_employees_in_training(employees, program, enrollment_date=None, target_completion_date=None, tenant=None):
    """
    Enroll multiple employees in a training program
    
    Returns:
        dict with success_count, failed_count, and details
    """
    results = {
        'success_count': 0,
        'failed_count': 0,
        'details': []
    }
    
    for employee in employees:
        enrollment, message = enroll_employee_in_training(
            employee, program, enrollment_date, target_completion_date, tenant=tenant
        )
        
        if enrollment:
            results['success_count'] += 1
            results['details'].append({
                'employee': employee.get_full_name(),
                'status': 'success',
                'message': message
            })
        else:
            results['failed_count'] += 1
            results['details'].append({
                'employee': employee.get_full_name(),
                'status': 'failed',
                'message': message
            })
    
    return results


def get_training_statistics(company, tenant=None):
    """Get comprehensive training statistics for a company"""
    from training.models import TrainingEnrollment, TrainingProgram
    from django.db.models import Count, Avg
    
    enrollments = TrainingEnrollment.objects.filter(employee__company=company)
    if tenant:
        enrollments = enrollments.filter(tenant=tenant)
    
    total_enrollments = enrollments.count()
    completed = enrollments.filter(status='COMPLETED').count()
    in_progress = enrollments.filter(status='IN_PROGRESS').count()
    not_started = enrollments.filter(status='NOT_STARTED').count()
    
    completion_rate = (completed / total_enrollments * 100) if total_enrollments > 0 else 0
    
    # Average score
    avg_score = enrollments.filter(status='COMPLETED', score__isnull=False).aggregate(
        avg=Avg('score')
    )['avg'] or 0
    
    # Programs by category
    programs = TrainingProgram.objects.filter(tenant=tenant, is_active=True)
    programs_by_category = programs.values('category').annotate(count=Count('id'))
    
    return {
        'total_enrollments': total_enrollments,
        'completed': completed,
        'in_progress': in_progress,
        'not_started': not_started,
        'completion_rate': round(completion_rate, 2),
        'average_score': round(avg_score, 2),
        'programs_by_category': list(programs_by_category),
        'total_programs': programs.count()
    }


def assign_mandatory_training(employees, program, due_date, tenant=None):
    """Assign mandatory training to employees"""
    results = bulk_enroll_employees_in_training(
        employees, program, 
        enrollment_date=timezone.now().date(),
        target_completion_date=due_date,
        tenant=tenant
    )
    
    # Send notifications to all enrolled employees
    from notifications.utils import bulk_notify
    
    enrolled_employees = [
        emp for emp, detail in zip(employees, results['details'])
        if detail['status'] == 'success'
    ]
    
    if enrolled_employees:
        bulk_notify(
            recipients=enrolled_employees,
            title=f"Mandatory Training Assigned: {program.name}",
            message=f"You have been assigned mandatory training '{program.name}'. Please complete by {due_date}.",
            notification_type='INFO',
            category='TRAINING',
            link='/training/',
            send_email=True,
            tenant=tenant
        )
    
    return results
