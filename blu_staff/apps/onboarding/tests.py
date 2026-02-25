from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from unittest.mock import patch

from blu_staff.apps.accounts.models import Company
from tenant_management.models import Tenant
from .models import (
    OnboardingChecklist,
    OnboardingTask,
    EmployeeOnboarding,
    EmployeeOffboarding,
    OffboardingChecklist,
    OnboardingTaskCompletion,
)


class OnboardingAdminEndpointsTests(TestCase):
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
        self.buddy = User.objects.create_user(
            email='buddy@example.com',
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

        self.onboarding_checklist = OnboardingChecklist.objects.create(
            tenant=self.tenant,
            name='Default Onboarding',
            is_default=True,
            is_active=True,
        )
        OnboardingTask.objects.create(
            tenant=self.tenant,
            checklist=self.onboarding_checklist,
            title='Welcome Session',
            order=1,
        )
        OnboardingTask.objects.create(
            tenant=self.tenant,
            checklist=self.onboarding_checklist,
            title='HR Paperwork',
            order=2,
        )

        self.offboarding_checklist = OffboardingChecklist.objects.create(
            tenant=self.tenant,
            name='Default Offboarding',
            is_default=True,
            is_active=True,
        )

        self.client.force_login(self.admin)

    @patch('ems_project.frontend_views.tenant_metadata_available', return_value=True)
    def test_admin_can_start_onboarding(self, _metadata):
        payload = {
            'employee': self.employee.id,
            'checklist': self.onboarding_checklist.id,
            'start_date': date.today().isoformat(),
            'expected_completion_date': (date.today() + timedelta(days=30)).isoformat(),
            'buddy': self.buddy.id,
            'notes': 'New hire onboarding',
        }

        response = self.client.post(reverse('onboarding_create'), data=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('id', data)
        onboarding = EmployeeOnboarding.objects.get(pk=data['id'])
        self.assertEqual(onboarding.employee, self.employee)
        self.assertEqual(onboarding.tenant, self.tenant)
        self.assertEqual(onboarding.status, EmployeeOnboarding.Status.NOT_STARTED)

        completions = OnboardingTaskCompletion.objects.filter(employee_onboarding=onboarding)
        self.assertEqual(completions.count(), 2)
        self.assertTrue(all(item.tenant == self.tenant for item in completions))

    @patch('ems_project.frontend_views.tenant_metadata_available', return_value=True)
    def test_onboarding_rejected_for_foreign_employee(self, _metadata):
        payload = {
            'employee': self.foreign_employee.id,
            'checklist': self.onboarding_checklist.id,
            'start_date': date.today().isoformat(),
            'expected_completion_date': (date.today() + timedelta(days=10)).isoformat(),
        }

        response = self.client.post(reverse('onboarding_create'), data=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json())
        self.assertEqual(EmployeeOnboarding.objects.count(), 0)

    @patch('ems_project.frontend_views.tenant_metadata_available', return_value=True)
    def test_employee_cannot_start_onboarding(self, _metadata):
        payload = {
            'employee': self.employee.id,
            'checklist': self.onboarding_checklist.id,
            'start_date': date.today().isoformat(),
            'expected_completion_date': (date.today() + timedelta(days=10)).isoformat(),
        }

        self.client.force_login(self.employee)
        response = self.client.post(reverse('onboarding_create'), data=payload)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(EmployeeOnboarding.objects.count(), 0)

    @patch('ems_project.frontend_views.tenant_metadata_available', return_value=True)
    def test_admin_can_start_offboarding(self, _metadata):
        payload = {
            'employee': self.employee.id,
            'checklist': self.offboarding_checklist.id,
            'last_working_date': (date.today() + timedelta(days=14)).isoformat(),
            'reason': EmployeeOffboarding.Reason.RESIGNATION,
            'notes': 'Leaving company',
            'exit_interview_completed': False,
        }

        response = self.client.post(reverse('offboarding_create'), data=payload)
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn('id', data)
        offboarding = EmployeeOffboarding.objects.get(pk=data['id'])
        self.assertEqual(offboarding.employee, self.employee)
        self.assertEqual(offboarding.tenant, self.tenant)
        self.assertEqual(offboarding.status, EmployeeOffboarding.Status.NOT_STARTED)

    @patch('ems_project.frontend_views.tenant_metadata_available', return_value=True)
    def test_offboarding_rejected_for_foreign_employee(self, _metadata):
        payload = {
            'employee': self.foreign_employee.id,
            'checklist': self.offboarding_checklist.id,
            'last_working_date': (date.today() + timedelta(days=7)).isoformat(),
            'reason': EmployeeOffboarding.Reason.RESIGNATION,
        }

        response = self.client.post(reverse('offboarding_create'), data=payload)
        self.assertEqual(response.status_code, 400)
        self.assertIn('errors', response.json())
        self.assertEqual(EmployeeOffboarding.objects.count(), 0)
