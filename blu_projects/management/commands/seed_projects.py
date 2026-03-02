import random
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.utils import timezone

from blu_projects.models import (
    Project, ProjectMilestone, Task, ProjectActivity, ProjectRisk, ProjectStakeholder
)

User = get_user_model()

PROJECTS = [
    {
        'name': 'Community Water Access Initiative',
        'code': 'CWAI-2025',
        'project_type': 'HUMANITARIAN',
        'sector': 'NGO',
        'methodology': 'PRINCE2',
        'status': 'IN_PROGRESS',
        'priority': 'HIGH',
        'risk_level': 'MEDIUM',
        'visibility': 'INTERNAL',
        'description': 'Providing clean water access to 10,000 rural beneficiaries across three districts.',
        'objectives': '• Install 25 borehole wells\n• Train 50 community water managers\n• Reach 10,000 beneficiaries by Q4 2025',
        'scope': 'In scope: site surveys, drilling, pump installation, community training\nOut of scope: ongoing maintenance after handover',
        'funding_source': 'USAID / World Bank',
        'grant_reference': 'AID-OAA-A-25-00042',
        'currency': 'USD',
        'budget': 450000,
        'funding_amount': 400000,
        'beneficiary_count': 10000,
        'client_name': 'Ministry of Water Resources',
        'client_organisation': 'Government of Ruritania',
        'client_email': 'water@gov.ruritania.org',
        'days_ago': 60,
        'duration': 180,
    },
    {
        'name': 'ERP System Migration & Rollout',
        'code': 'ERP-MIGRATE-25',
        'project_type': 'IT_SOFTWARE',
        'sector': 'TECHNOLOGY',
        'methodology': 'AGILE',
        'status': 'IN_PROGRESS',
        'priority': 'CRITICAL',
        'risk_level': 'HIGH',
        'visibility': 'INTERNAL',
        'description': 'Full migration from legacy ERP to cloud-based SAP S/4HANA.',
        'objectives': '• Migrate all 8 departments by Q3 2025\n• Zero downtime cutover\n• Train 200 staff members',
        'scope': 'In scope: data migration, integrations, training, UAT\nOut of scope: hardware procurement, network upgrades',
        'funding_source': 'Internal IT Budget',
        'grant_reference': 'IT-CAP-2025-003',
        'currency': 'USD',
        'budget': 280000,
        'funding_amount': None,
        'beneficiary_count': None,
        'client_name': 'Internal — All Departments',
        'client_organisation': '',
        'client_email': '',
        'days_ago': 30,
        'duration': 270,
    },
    {
        'name': 'Youth Skills & Employability Programme',
        'code': 'YSEP-2025',
        'project_type': 'GRANT',
        'sector': 'EDUCATION',
        'methodology': 'LEAN',
        'status': 'PLANNING',
        'priority': 'HIGH',
        'risk_level': 'LOW',
        'visibility': 'PUBLIC',
        'description': 'Vocational training and job placement for 500 unemployed youth aged 18–30.',
        'objectives': '• Train 500 youth in vocational skills\n• Achieve 70% job placement rate\n• Partner with 30+ employers',
        'scope': 'In scope: training delivery, job fairs, mentorship\nOut of scope: bursaries, transport subsidies',
        'funding_source': 'European Union – Skills Development Fund',
        'grant_reference': 'EU-SDF-2025-RU-114',
        'currency': 'EUR',
        'budget': 320000,
        'funding_amount': 300000,
        'beneficiary_count': 500,
        'client_name': 'EU Delegation',
        'client_organisation': 'European Union',
        'client_email': 'delegation@eu.int',
        'days_ago': 10,
        'duration': 365,
    },
    {
        'name': 'District Hospital Construction – Block C',
        'code': 'DHC-BLOCKC-25',
        'project_type': 'INFRASTRUCTURE',
        'sector': 'HEALTHCARE',
        'methodology': 'WATERFALL',
        'status': 'IN_PROGRESS',
        'priority': 'HIGH',
        'risk_level': 'HIGH',
        'visibility': 'INTERNAL',
        'description': 'Construction of 60-bed patient ward and surgical theatre block.',
        'objectives': '• Complete structural works by Month 6\n• Pass all safety inspections\n• Hand over to hospital management by Month 12',
        'scope': 'In scope: foundations, structure, roofing, fitout, utilities\nOut of scope: medical equipment, furniture',
        'funding_source': 'Ministry of Health – Capital Budget',
        'grant_reference': 'MOH-CAP-C-2025-07',
        'currency': 'USD',
        'budget': 1200000,
        'funding_amount': 1200000,
        'beneficiary_count': 50000,
        'client_name': 'District Health Authority',
        'client_organisation': 'Ministry of Health',
        'client_email': 'capital@moh.gov',
        'days_ago': 45,
        'duration': 365,
    },
    {
        'name': 'Mobile Banking App – v2.0 Launch',
        'code': 'MBANK-V2-25',
        'project_type': 'CLIENT',
        'sector': 'FINANCE',
        'methodology': 'AGILE',
        'status': 'IN_PROGRESS',
        'priority': 'CRITICAL',
        'risk_level': 'MEDIUM',
        'visibility': 'RESTRICTED',
        'description': 'Redesign and relaunch of mobile banking app with biometric authentication.',
        'objectives': '• Release v2.0 to 250,000 active users\n• Achieve 4.5+ app store rating\n• Reduce support tickets by 30%',
        'scope': 'In scope: iOS/Android apps, API gateway, QA, security audit\nOut of scope: core banking backend changes',
        'funding_source': 'Client Contract – First National Bank',
        'grant_reference': 'FNB-CONTRACT-2025-09',
        'currency': 'USD',
        'budget': 195000,
        'funding_amount': 195000,
        'beneficiary_count': None,
        'client_name': 'James Kariuki',
        'client_organisation': 'First National Bank',
        'client_email': 'jkariuki@fnb.co',
        'days_ago': 20,
        'duration': 180,
    },
]

TASK_TEMPLATES = [
    ('Requirements Gathering', 'COMPLETED', 'HIGH'),
    ('Stakeholder Kickoff Meeting', 'COMPLETED', 'HIGH'),
    ('Project Charter Approval', 'COMPLETED', 'MEDIUM'),
    ('Procurement & Vendor Selection', 'IN_PROGRESS', 'HIGH'),
    ('Site Survey / Discovery Phase', 'IN_PROGRESS', 'MEDIUM'),
    ('Risk Assessment & Register', 'IN_PROGRESS', 'HIGH'),
    ('Design & Architecture', 'IN_PROGRESS', 'MEDIUM'),
    ('Development / Implementation Phase 1', 'IN_PROGRESS', 'HIGH'),
    ('Testing & Quality Assurance', 'TODO', 'MEDIUM'),
    ('User Acceptance Testing (UAT)', 'TODO', 'HIGH'),
    ('Training Delivery', 'TODO', 'MEDIUM'),
    ('Monitoring & Evaluation', 'TODO', 'LOW'),
    ('Final Report Submission', 'TODO', 'MEDIUM'),
    ('Project Closeout & Handover', 'TODO', 'HIGH'),
]

RISK_TEMPLATES = [
    ('Funding disbursement delays', 'FINANCIAL', 3, 4),
    ('Key staff turnover', 'OPERATIONAL', 2, 3),
    ('Regulatory or compliance changes', 'COMPLIANCE', 2, 4),
    ('Scope creep from stakeholders', 'STRATEGIC', 3, 3),
    ('Supply chain / procurement delays', 'OPERATIONAL', 3, 3),
    ('Security breach or data loss', 'TECHNICAL', 2, 5),
]

STAKEHOLDER_TEMPLATES = [
    ('Project Sponsor', 'SPONSOR', 'HIGH', 'HIGH'),
    ('Donor Representative', 'DONOR', 'HIGH', 'MEDIUM'),
    ('End User Community', 'COMMUNITY', 'LOW', 'HIGH'),
    ('Technical Regulator', 'REGULATOR', 'HIGH', 'LOW'),
    ('Primary Supplier', 'SUPPLIER', 'MEDIUM', 'MEDIUM'),
]

MILESTONE_TEMPLATES = [
    ('Inception & Planning Complete', 30),
    ('Phase 1 Delivery', 90),
    ('Mid-Project Review', 150),
    ('Phase 2 Delivery', 210),
    ('Project Handover & Closure', 270),
]


class Command(BaseCommand):
    help = 'Seed BLU Projects with realistic mock data across all org types'

    def add_arguments(self, parser):
        parser.add_argument(
            '--company-id',
            type=int,
            help='Company ID to create projects for (defaults to first company found)',
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='User ID to use as project creator / manager',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Delete existing seed projects before creating new ones',
        )

    def handle(self, *args, **options):
        # Resolve user
        user_id = options.get('user_id')
        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stderr.write(self.style.ERROR(f'User {user_id} not found.'))
                return
        else:
            user = User.objects.filter(is_staff=True).first() or User.objects.first()

        if not user:
            self.stderr.write(self.style.ERROR('No users found. Create a user first.'))
            return

        company = user.company
        if not company:
            # Fall back: find any available company
            from blu_staff.apps.accounts.models import Company
            company = Company.objects.first()
            if not company:
                self.stderr.write(self.style.ERROR(
                    'No company found. Create a company in the admin panel first.'))
                return
            self.stdout.write(self.style.WARNING(
                f'User has no company. Using first available: {company}'))

        self.stdout.write(f'Seeding projects for company: {company} (user: {user})')

        # Optionally clear
        if options.get('clear'):
            deleted, _ = Project.objects.filter(company=company, code__in=[p['code'] for p in PROJECTS]).delete()
            self.stdout.write(self.style.WARNING(f'Cleared {deleted} existing seed projects'))

        team_users = list(User.objects.filter(company=company)[:10])

        created_count = 0
        for pdata in PROJECTS:
            if Project.objects.filter(company=company, code=pdata['code']).exists():
                self.stdout.write(f'  Skipping existing: {pdata["code"]}')
                continue

            start = date.today() - timedelta(days=pdata['days_ago'])
            end = start + timedelta(days=pdata['duration'])

            project = Project.objects.create(
                company=company,
                created_by=user,
                project_manager=user,
                name=pdata['name'],
                code=pdata['code'],
                project_type=pdata['project_type'],
                sector=pdata['sector'],
                methodology=pdata['methodology'],
                status=pdata['status'],
                priority=pdata['priority'],
                risk_level=pdata['risk_level'],
                visibility=pdata['visibility'],
                description=pdata['description'],
                objectives=pdata['objectives'],
                scope=pdata['scope'],
                funding_source=pdata['funding_source'],
                grant_reference=pdata['grant_reference'],
                currency=pdata['currency'],
                budget=pdata['budget'],
                funding_amount=pdata['funding_amount'],
                beneficiary_count=pdata['beneficiary_count'],
                client_name=pdata['client_name'],
                client_organisation=pdata['client_organisation'],
                client_email=pdata['client_email'],
                start_date=start,
                end_date=end,
                tags=f"{pdata['sector'].lower()}, {pdata['project_type'].lower()}, 2025",
            )

            # Team members
            if team_users:
                project.team_members.set(random.sample(team_users, min(4, len(team_users))))

            # Tasks
            for i, (title, status, priority) in enumerate(TASK_TEMPLATES):
                due = start + timedelta(days=random.randint(20, pdata['duration'] - 10))
                assignee = random.choice(team_users) if team_users else None
                Task.objects.create(
                    project=project,
                    title=title,
                    status=status,
                    priority=priority,
                    assigned_to=assignee,
                    due_date=due,
                    story_points=random.choice([1, 2, 3, 5, 8, 13]),
                    label=random.choice(['backend', 'frontend', 'design', 'analysis', 'testing', '']),
                    description=f'Task: {title} for project {project.code}',
                )

            # Milestones
            for ms_name, offset_days in MILESTONE_TEMPLATES:
                ms_date = start + timedelta(days=offset_days)
                ms_status = 'COMPLETED' if ms_date < date.today() else 'PENDING'
                ProjectMilestone.objects.create(
                    project=project,
                    name=ms_name,
                    due_date=ms_date,
                    status=ms_status,
                )

            # Risks
            for risk_title, category, prob, impact in RISK_TEMPLATES[:4]:
                ProjectRisk.objects.create(
                    project=project,
                    title=risk_title,
                    category=category,
                    probability=prob,
                    impact=impact,
                    status='OPEN',
                    mitigation_plan=f'Monthly monitoring and escalation protocol for: {risk_title}',
                    contingency_plan=f'Activate contingency reserve and notify steering committee.',
                )

            # Stakeholders
            sh_names = [
                ('Patricia Osei', 'paosei@donor.org'),
                ('Mohammed Al-Farsi', 'mfarsi@gov.org'),
                ('Jane Müller', 'jmuller@partner.eu'),
                ('David Chirwa', 'dchirwa@supplier.co'),
                ('Community Representative', 'community@local.org'),
            ]
            for (sh_name, sh_email), (sh_role, role_key, influence, interest) in zip(
                sh_names, STAKEHOLDER_TEMPLATES
            ):
                ProjectStakeholder.objects.create(
                    project=project,
                    name=sh_name,
                    organisation=pdata['client_organisation'] or 'External',
                    role=role_key,
                    email=sh_email,
                    influence=influence,
                    interest=interest,
                    engagement_strategy=f'Quarterly meetings, monthly reports, and ad-hoc escalation as needed.',
                )

            # Activity log
            ProjectActivity.objects.create(
                project=project,
                user=user,
                action='CREATED',
                description=f"Project '{project.name}' created via seed command",
            )

            created_count += 1
            self.stdout.write(self.style.SUCCESS(f'  Created: [{project.code}] {project.name}'))

        self.stdout.write(self.style.SUCCESS(
            f'\nDone! Created {created_count} projects with tasks, milestones, risks & stakeholders.'
        ))
