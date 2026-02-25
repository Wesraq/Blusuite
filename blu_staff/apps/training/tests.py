from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from blu_staff.apps.accounts.models import Company
from tenant_management.models import Tenant
from .models import TrainingProgram, TrainingEnrollment


class TrainingAdminEndpointsTests(TestCase):
    def setUp(self):
        User = get_user_model()

        self.company = Company.objects.create(
            name='Acme Corp',
            address='123 Test Street',
            subscription_plan='BASIC',
            max_employees=100,
            is_approved=True,
            is_active=True,
        )
        self.tenant = Tenant.objects.create(name='Acme Tenant', slug='acme', company=self.company)

        self.admin = User.objects.create_user(
            email='admin@example.com',
            password='pass1234',
            role=User.Role.EMPLOYER_ADMIN,
            company=self.company,
        )
        self.employee = User.objects.create_user(
            email='employee@example.com',
            password='pass1234',
            role=User.Role.EMPLOYEE,
            company=self.company,
        )

        self.other_company = Company.objects.create(
            name='Other Corp',
            address='999 Elsewhere',
            subscription_plan='BASIC',
            max_employees=50,
            is_approved=True,
            is_active=True,
        )
        self.other_tenant = Tenant.objects.create(name='Other Tenant', slug='other', company=self.other_company)
        self.foreign_employee = User.objects.create_user(
            email='foreign@example.com',
            password='pass1234',
            role=User.Role.EMPLOYEE,
            company=self.other_company,
        )

        self.client.force_login(self.admin)

    @patch('ems_project.frontend_views.tenant_metadata_available', return_value=True)
    def test_admin_can_create_training_program(self, _metadata):
        payload = {
            'title': 'Safety Orientation',
            'description': 'Introductory safety session.',
            'program_type': TrainingProgram.ProgramType.SAFETY,
            'duration_hours': '2.5',
            'cost': '0',
            'provider': 'Internal',
            'instructor': 'Jane Trainer',
        }

        response = self.client.post(reverse('training_program_create'), data=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('id', data)
        program = TrainingProgram.objects.get(pk=data['id'])
        self.assertEqual(program.title, 'Safety Orientation')
        self.assertEqual(program.tenant, self.tenant)
        self.assertEqual(program.created_by, self.admin)

    @patch('ems_project.frontend_views.tenant_metadata_available', return_value=True)
    def test_employee_cannot_create_training_program(self, _metadata):
        self.client.force_login(self.employee)
        response = self.client.post(reverse('training_program_create'), data={})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(TrainingProgram.objects.count(), 0)

    @patch('ems_project.frontend_views.tenant_metadata_available', return_value=True)
    def test_admin_can_enroll_employee_in_program(self, _metadata):
        program = TrainingProgram.objects.create(
            tenant=self.tenant,
            title='Leadership Basics',
            description='Improve leadership skills',
            program_type=TrainingProgram.ProgramType.LEADERSHIP,
            duration_hours=3,
            cost=0,
            provider='Internal',
            instructor='John Coach',
        )

        payload = {
            'employee': self.employee.id,
            'program': program.id,
            'enrollment_date': date.today().isoformat(),
            'start_date': date.today().isoformat(),
            'status': TrainingEnrollment.Status.ENROLLED,
            'notes': 'Initial enrollment',
        }

        response = self.client.post(reverse('training_enrollment_create'), data=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('id', data)
        enrollment = TrainingEnrollment.objects.get(pk=data['id'])
        self.assertEqual(enrollment.employee, self.employee)
        self.assertEqual(enrollment.program, program)
        self.assertEqual(enrollment.tenant, self.tenant)

    @patch('ems_project.frontend_views.tenant_metadata_available', return_value=True)
    def test_enrollment_rejected_for_employee_of_another_company(self, _metadata):
        program = TrainingProgram.objects.create(
            tenant=self.tenant,
            title='Compliance 101',
            description='Compliance overview',
            program_type=TrainingProgram.ProgramType.COMPLIANCE,
            duration_hours=1,
            cost=0,
            provider='Internal',
            instructor='Compliance Officer',
        )

        payload = {
            'employee': self.foreign_employee.id,
            'program': program.id,
            'enrollment_date': date.today().isoformat(),
            'start_date': date.today().isoformat(),
            'status': TrainingEnrollment.Status.ENROLLED,
            'notes': 'Wrong company enrollment',
        }

        response = self.client.post(reverse('training_enrollment_create'), data=payload)
        self.assertEqual(response.status_code, 400)
        response_data = response.json()
        self.assertIn('errors', response_data)
        self.assertIn('employee', response_data['errors'])
        self.assertEqual(TrainingEnrollment.objects.count(), 0)
