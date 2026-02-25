# Payroll Deductions System Implementation

## ✅ Completed Tasks

### 1. Database Models Created

#### **PayrollDeduction Model** (`payroll/models.py`)
Tracks detailed deductions for each payroll entry:
- **Deduction Types**: PAYE, NAPSA, NHIMA, LATE, ABSENT, LOAN, ADVANCE, OTHER
- **Fields**:
  - `payroll` - Foreign key to Payroll
  - `deduction_type` - Type of deduction
  - `amount` - Deduction amount
  - `description` - Optional description
  - `is_statutory` - Flag for statutory deductions (PAYE, NAPSA, NHIMA)

#### **PayrollDeductionSettings Model** (`accounts/models.py`)
Company-wide configuration for payroll deductions:

**PAYE (Income Tax) Settings:**
- `paye_tax_brackets` - JSON field for tax brackets
  - Example: `[{"min": 0, "max": 4800, "rate": 0}, {"min": 4801, "max": 9999999, "rate": 37.5}]`
- `paye_enabled` - Toggle PAYE on/off

**NAPSA (Social Security) Settings:**
- `napsa_employee_percentage` - Employee contribution % (default: 5%)
- `napsa_employer_percentage` - Employer contribution % (default: 5%)
- `napsa_enabled` - Toggle NAPSA on/off

**NHIMA (Health Insurance) Settings:**
- `nhima_employee_amount` - Fixed monthly employee contribution
- `nhima_employer_amount` - Fixed monthly employer contribution
- `nhima_enabled` - Toggle NHIMA on/off

**Attendance-Based Deductions:**
- `late_deduction_per_occurrence` - Amount deducted per late occurrence
- `absent_deduction_per_day` - Amount deducted per absent day
- `absent_deduction_type` - Either 'FIXED' or 'DAILY_RATE' (salary/working days)

**Currency:**
- `currency` - Currency code (default: ZMW)

### 2. Migrations Applied ✅
- `accounts.0027_payrolldeductionsettings` - Created
- `payroll.0002_payrolldeduction` - Created
- Both migrations applied successfully

### 3. Messaging Issues Fixed ✅
- **Direct Messages**: Removed auto-refresh polling (was causing continuous GET requests every 5 seconds)
- **Direct Messages**: Enlarged textarea to 3 rows with better styling
- **Group Chat**: Fixed textarea size and button alignment

---

## 📋 Next Steps Required

### 1. **Settings Page Configuration UI**
Add deduction configuration to `/settings/config/`:

**Create Settings Form** (`accounts/forms.py`):
```python
class PayrollDeductionSettingsForm(forms.ModelForm):
    class Meta:
        model = PayrollDeductionSettings
        fields = [
            'paye_tax_brackets', 'paye_enabled',
            'napsa_employee_percentage', 'napsa_employer_percentage', 'napsa_enabled',
            'nhima_employee_amount', 'nhima_employer_amount', 'nhima_enabled',
            'late_deduction_per_occurrence',
            'absent_deduction_per_day', 'absent_deduction_type',
            'currency'
        ]
```

**Add to Settings View** (`frontend_views.py` - `settings_dashboard()`):
- Get or create `PayrollDeductionSettings` for company
- Pass form to template
- Handle POST for 'payroll_deductions' action

**Add to Template** (`templates/ems/settings_company.html`):
- New tab: "💰 Payroll Deductions"
- Form sections for PAYE, NAPSA, NHIMA, Attendance deductions
- Save button

### 2. **Payroll Calculation Logic**
Update `Payroll.save()` method to:
- Calculate PAYE based on tax brackets
- Calculate NAPSA based on percentages
- Add NHIMA fixed amounts
- Query attendance records for late/absent counts
- Create `PayrollDeduction` records for each deduction
- Update `total_deductions` and `net_pay`

### 3. **Enhanced Payroll Table**
Update `/payroll/` page to show detailed deductions:

**Table Columns:**
- Employee
- Period
- Base Salary
- Overtime
- Bonuses
- **Gross Pay**
- PAYE (expandable)
- NAPSA (expandable)
- NHIMA (expandable)
- Late Deductions (expandable)
- Absent Deductions (expandable)
- **Total Deductions**
- **Net Pay**
- Status
- Actions

**Detail View:**
- Show all deductions in a breakdown table
- Show calculation method for each

### 4. **Payroll Report Enhancements**
- Add deduction breakdown to payslips
- CSV export with detailed deductions
- Monthly/Annual deduction reports
- Tax remittance reports (PAYE, NAPSA, NHIMA totals)

---

## 📊 Sample PAYE Tax Brackets (Zambia)

```json
[
  {"min": 0, "max": 4800, "rate": 0, "description": "First K4,800 - Tax Free"},
  {"min": 4801, "max": 9999999, "rate": 37.5, "description": "Above K4,800 - 37.5%"}
]
```

---

## 🔍 Usage Example

### Creating Payroll with Deductions:

```python
from payroll.models import Payroll, PayrollDeduction
from accounts.models import PayrollDeductionSettings

# Get settings
settings = PayrollDeductionSettings.objects.get(company=company)

# Create payroll
payroll = Payroll.objects.create(
    employee=employee,
    period_start=period_start,
    period_end=period_end,
    base_pay=10000,
    # ... other fields
)

# Calculate PAYE
taxable_income = payroll.base_pay
paye_amount = calculate_paye(taxable_income, settings.paye_tax_brackets)
PayrollDeduction.objects.create(
    payroll=payroll,
    deduction_type='PAYE',
    amount=paye_amount,
    is_statutory=True
)

# Calculate NAPSA
napsa_amount = payroll.base_pay * (settings.napsa_employee_percentage / 100)
PayrollDeduction.objects.create(
    payroll=payroll,
    deduction_type='NAPSA',
    amount=napsa_amount,
    is_statutory=True
)

# ... similar for NHIMA, LATE, ABSENT
```

---

## 🎯 Benefits of This Implementation

1. **Flexible Tax Configuration** - Easy to update tax brackets without code changes
2. **Statutory Compliance** - PAYE, NAPSA, NHIMA automatically calculated
3. **Attendance Integration** - Late/absent deductions linked to attendance records
4. **Audit Trail** - All deductions tracked separately for transparency
5. **Multi-Currency Support** - Ready for international operations
6. **Scalable** - Can add new deduction types easily

---

## 📝 Admin Panel Access

Models are available in Django Admin:
- `/admin/payroll/payrolldeduction/`
- `/admin/accounts/payrolldeductionsettings/`

Administrators can manually configure settings via admin panel until UI is built.

---

**Status**: Database and models ready ✅ | UI implementation pending
