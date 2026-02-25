# 🏗️ Multi-Tenant Payslip Design Architecture

## ✅ **ALL BUGS FIXED**

### **Issues Fixed:**
1. ✅ **Portrait/Landscape toggle** - Now properly switches styles and button highlights
2. ✅ **Logo position buttons** - Updates live preview positioning
3. ✅ **Stamp position buttons** - Updates footer layout
4. ✅ **Load recommended fields** - Properly populates canvas
5. ✅ **Display element checkboxes** - Toggle logo/stamp visibility in preview
6. ✅ **Field layout** - Fields now display vertically (not side-by-side)

---

## 🏢 **Multi-Tenant Design System**

### **Architecture: 3-Tier Fallback System**

```
┌──────────────────────────────────────────────┐
│ TIER 1: SYSTEM DEFAULT                      │
│ - Built-in professional template            │
│ - Always available as fallback              │
│ - Cannot be deleted                          │
│ - Used for new tenants                       │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ TIER 2: COMPANY CUSTOM DESIGN                │
│ - Saved per company in Company model        │
│ - Fields: payslip_section_order (JSON)      │
│ - Layout: payslip_header_style              │
│ - Colors: header, accent, section            │
│ - Overrides system default when exists      │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ TIER 3: GENERATED PDF                       │
│ - Uses company design OR system default     │
│ - Populated with actual payroll data        │
│ - Ready for download/email                  │
└──────────────────────────────────────────────┘
```

---

## 📁 **Implementation Files**

### **1. Create Constants File**

**File:** `payroll/constants.py` (NEW)

```python
"""
Default payslip configuration for multi-tenant system.
These defaults are used when a company hasn't customized their design.
"""

# System Default Field Order
DEFAULT_PAYSLIP_FIELDS = [
    # Employee Information
    'employee_name',
    'employee_id',
    'position',
    'department',
    'pay_period',
    
    # Earnings
    'basic_salary',
    'housing_allowance',
    'transport_allowance',
    'other_allowances',
    'gross_pay',
    
    # Deductions
    'napsa',
    'nhima',
    'paye',
    'loans',
    'advances',
    
    # Totals
    'total_allowances',
    'total_deductions',
    'net_pay'
]

# System Default Colors
DEFAULT_PAYSLIP_COLORS = {
    'header': '#3b82f6',      # Blue
    'accent': '#10b981',      # Green
    'section': '#C5D9F1'      # Light Blue (MFI style)
}

# System Default Layout
DEFAULT_PAYSLIP_LAYOUT = 'professional_table'

# Field Definitions (for reference)
PAYSLIP_FIELD_DEFINITIONS = {
    # Employee Info
    'employee_name': {'label': 'Employee Name', 'template': '{{employee.full_name}}', 'category': 'employee'},
    'employee_id': {'label': 'Employee ID', 'template': '{{employee.employee_id}}', 'category': 'employee'},
    'position': {'label': 'Position', 'template': '{{employee.position}}', 'category': 'employee'},
    'department': {'label': 'Department', 'template': '{{employee.department}}', 'category': 'employee'},
    'hire_date': {'label': 'Hire Date', 'template': '{{employee.hire_date}}', 'category': 'employee'},
    'email': {'label': 'Email', 'template': '{{employee.email}}', 'category': 'employee'},
    'phone': {'label': 'Phone', 'template': '{{employee.phone}}', 'category': 'employee'},
    
    # Salary & Earnings
    'basic_salary': {'label': 'Basic Salary', 'template': '{{payroll.basic_salary}}', 'category': 'salary'},
    'pay_period': {'label': 'Pay Period', 'template': '{{payroll.period}}', 'category': 'salary'},
    'payment_date': {'label': 'Payment Date', 'template': '{{payroll.payment_date}}', 'category': 'salary'},
    'housing_allowance': {'label': 'Housing Allowance', 'template': '{{payroll.housing_allowance}}', 'category': 'salary'},
    'transport_allowance': {'label': 'Transport Allowance', 'template': '{{payroll.transport_allowance}}', 'category': 'salary'},
    'other_allowances': {'label': 'Other Allowances', 'template': '{{payroll.other_allowances}}', 'category': 'salary'},
    'overtime': {'label': 'Overtime', 'template': '{{payroll.overtime}}', 'category': 'salary'},
    'bonus': {'label': 'Bonus', 'template': '{{payroll.bonus}}', 'category': 'salary'},
    
    # Deductions
    'paye': {'label': 'PAYE Tax', 'template': '{{payroll.paye}}', 'category': 'deductions'},
    'napsa': {'label': 'NAPSA', 'template': '{{payroll.napsa}}', 'category': 'deductions'},
    'nhima': {'label': 'NHIMA', 'template': '{{payroll.nhima}}', 'category': 'deductions'},
    'loans': {'label': 'Loans', 'template': '{{payroll.loans}}', 'category': 'deductions'},
    'advances': {'label': 'Salary Advances', 'template': '{{payroll.advances}}', 'category': 'deductions'},
    'other_deductions': {'label': 'Other Deductions', 'template': '{{payroll.other_deductions}}', 'category': 'deductions'},
    
    # Tax Information
    'gross_pay': {'label': 'Gross Pay', 'template': '{{payroll.gross_pay}}', 'category': 'tax'},
    'taxable_income': {'label': 'Taxable Income', 'template': '{{payroll.taxable_income}}', 'category': 'tax'},
    'tax_rate': {'label': 'Tax Rate', 'template': '{{payroll.tax_rate}}%', 'category': 'tax'},
    
    # Totals
    'total_allowances': {'label': 'Total Allowances', 'template': '{{payroll.total_allowances}}', 'category': 'totals'},
    'total_deductions': {'label': 'Total Deductions', 'template': '{{payroll.total_deductions}}', 'category': 'totals'},
    'net_pay': {'label': 'Net Pay', 'template': '{{payroll.net_pay}}', 'category': 'totals', 'highlight': True}
}
```

---

### **2. Create Helper Functions**

**File:** `payroll/utils.py` (NEW or ADD TO EXISTING)

```python
from .constants import (
    DEFAULT_PAYSLIP_FIELDS,
    DEFAULT_PAYSLIP_COLORS,
    DEFAULT_PAYSLIP_LAYOUT,
    PAYSLIP_FIELD_DEFINITIONS
)

def get_payslip_design(company):
    """
    Get company's custom payslip design or fall back to system default.
    
    Args:
        company: Company model instance
        
    Returns:
        dict: {
            'fields': list of field IDs,
            'layout': layout style string,
            'colors': dict of color values,
            'is_custom': boolean indicating if using custom design
        }
    """
    
    # Check if company has custom design
    has_custom_fields = company.payslip_section_order and len(company.payslip_section_order) > 0
    has_custom_layout = company.payslip_header_style and company.payslip_header_style != ''
    
    if has_custom_fields or has_custom_layout:
        # Use company's custom design
        return {
            'fields': company.payslip_section_order if has_custom_fields else DEFAULT_PAYSLIP_FIELDS,
            'layout': company.payslip_header_style or DEFAULT_PAYSLIP_LAYOUT,
            'colors': {
                'header': company.payslip_header_color or DEFAULT_PAYSLIP_COLORS['header'],
                'accent': company.payslip_accent_color or DEFAULT_PAYSLIP_COLORS['accent'],
                'section': getattr(company, 'payslip_section_color', None) or DEFAULT_PAYSLIP_COLORS['section']
            },
            'logo_position': company.payslip_logo_position or 'top-left',
            'stamp_position': company.payslip_stamp_position or 'bottom-right',
            'footer_text': company.payslip_footer_text or 'This is a computer-generated payslip and does not require a signature.',
            'show_logo': company.show_company_logo,
            'show_stamp': company.show_company_stamp,
            'show_signature': company.show_signature,
            'show_tax_breakdown': company.show_tax_breakdown,
            'is_custom': True
        }
    else:
        # Use system default
        return {
            'fields': DEFAULT_PAYSLIP_FIELDS,
            'layout': DEFAULT_PAYSLIP_LAYOUT,
            'colors': DEFAULT_PAYSLIP_COLORS,
            'logo_position': 'top-left',
            'stamp_position': 'bottom-right',
            'footer_text': 'This is a computer-generated payslip and does not require a signature.',
            'show_logo': True,
            'show_stamp': True,
            'show_signature': False,
            'show_tax_breakdown': True,
            'is_custom': False
        }


def get_field_definition(field_id):
    """Get field definition by ID."""
    return PAYSLIP_FIELD_DEFINITIONS.get(field_id, {
        'label': field_id.replace('_', ' ').title(),
        'template': f'{{{{payroll.{field_id}}}}}',
        'category': 'other'
    })


def get_fields_for_payslip(company):
    """
    Get list of field definitions for payslip generation.
    
    Returns:
        list: [{
            'id': 'employee_name',
            'label': 'Employee Name',
            'template': '{{employee.full_name}}',
            'category': 'employee'
        }, ...]
    """
    design = get_payslip_design(company)
    fields = []
    
    for field_id in design['fields']:
        field_def = get_field_definition(field_id)
        fields.append({
            'id': field_id,
            'label': field_def['label'],
            'template': field_def['template'],
            'category': field_def['category'],
            'highlight': field_def.get('highlight', False)
        })
    
    return fields


def can_reset_to_default(company):
    """Check if company has customized design that can be reset."""
    return (company.payslip_section_order and len(company.payslip_section_order) > 0) or \
           (company.payslip_header_style and company.payslip_header_style != '')


def reset_to_default_design(company):
    """Reset company's payslip design to system default."""
    company.payslip_section_order = []
    company.payslip_header_style = DEFAULT_PAYSLIP_LAYOUT
    company.payslip_header_color = DEFAULT_PAYSLIP_COLORS['header']
    company.payslip_accent_color = DEFAULT_PAYSLIP_COLORS['accent']
    company.payslip_section_color = DEFAULT_PAYSLIP_COLORS['section']
    company.save()
    return True
```

---

### **3. Update PDF Generation View**

**File:** `payroll/views.py` (UPDATE EXISTING)

```python
from .utils import get_payslip_design, get_fields_for_payslip
from django.template.loader import render_to_string
from weasyprint import HTML

def generate_payslip_pdf(request, payroll_id):
    """
    Generate PDF payslip for a specific payroll record.
    Uses company's custom design or system default.
    """
    payroll = get_object_or_404(Payroll, id=payroll_id)
    employee = payroll.employee
    company = payroll.company
    
    # Get design configuration (custom or default)
    design = get_payslip_design(company)
    fields = get_fields_for_payslip(company)
    
    # Choose template based on layout style
    template_map = {
        'professional_table': 'payroll/payslip_professional_table.html',
        'logo_left': 'payroll/payslip_logo_left.html',
        'logo_center': 'payroll/payslip_logo_center.html',
        'logo_right': 'payroll/payslip_logo_right.html',
        'modern_gradient': 'payroll/payslip_modern.html',
    }
    
    template = template_map.get(design['layout'], 'payroll/payslip_professional_table.html')
    
    # Prepare context
    context = {
        'payroll': payroll,
        'employee': employee,
        'company': company,
        'design': design,
        'fields': fields,
        'is_custom_design': design['is_custom']
    }
    
    # Render HTML
    html_string = render_to_string(template, context)
    
    # Generate PDF
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    
    # Return as response
    response = HttpResponse(pdf, content_type='application/pdf')
    filename = f'payslip_{employee.employee_id}_{payroll.period}.pdf'
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    
    return response
```

---

### **4. Add "Reset to Default" Button (Optional)**

**In:** `templates/ems/settings_company.html`

Add this button next to "Load Recommended Fields":

```html
<button type="button" id="resetToDefaultBtn" style="width: 100%; margin-top: 8px; padding: 10px; background: #ef4444; color: white; border: none; border-radius: 6px; font-size: 13px; font-weight: 500; cursor: pointer; transition: all 0.2s;">
  🔄 Reset to System Default
</button>
```

Add JavaScript:

```javascript
// Reset to Default button
const resetBtn = document.getElementById('resetToDefaultBtn');
if (resetBtn) {
  resetBtn.addEventListener('click', function() {
    if (confirm('This will reset your payslip design to the system default. Are you sure?')) {
      // Clear all fields
      droppedSections.innerHTML = '';
      sectionOrder = [];
      emptyState.style.display = 'flex';
      droppedSections.style.display = 'none';
      
      // Reset colors to default
      if (headerColorInput) headerColorInput.value = '#3b82f6';
      if (accentColorInput) accentColorInput.value = '#10b981';
      
      // Show success
      this.innerHTML = '✅ Reset Complete!';
      this.style.background = '#059669';
      
      setTimeout(() => {
        this.innerHTML = '🔄 Reset to System Default';
        this.style.background = '#ef4444';
      }, 2000);
    }
  });
}
```

---

## 🔄 **How It Works**

### **For New Tenants:**
1. Company registers
2. No custom design exists → `payslip_section_order` is empty
3. `get_payslip_design()` returns system default
4. Professional payslips generated immediately
5. Company can customize later

### **For Existing Tenants:**
1. Company opens Payslip Designer
2. Selects "Professional Table Layout"
3. Clicks "Load Recommended Fields"
4. Customizes colors, adds/removes fields
5. Clicks "Save Design"
6. `payslip_section_order` saved to database
7. `get_payslip_design()` returns custom design
8. Future payslips use custom design

### **For Tenants Who Want to Reset:**
1. Click "Reset to System Default" button
2. Confirm action
3. `reset_to_default_design()` clears custom design
4. Back to system default

---

## 📊 **Database Schema**

### **Company Model Fields:**
```python
# Layout & Style
payslip_header_style = CharField(default='professional_table')
payslip_orientation = CharField(default='portrait')

# Colors
payslip_header_color = CharField(default='#3b82f6')
payslip_accent_color = CharField(default='#10b981')
payslip_section_color = CharField(default='#C5D9F1')  # NEW!

# Field Selection
payslip_section_order = JSONField(default=list)  # ['employee_name', 'employee_id', ...]

# Positioning
payslip_logo_position = CharField(default='top-left')
payslip_stamp_position = CharField(default='bottom-right')

# Display Options
show_company_logo = BooleanField(default=True)
show_company_stamp = BooleanField(default=True)
show_signature = BooleanField(default=True)
show_tax_breakdown = BooleanField(default=True)

# Footer
payslip_footer_text = TextField(default='...')
```

---

## ✅ **Benefits of This Architecture**

1. **Scalability** - Supports unlimited tenants, each with custom design
2. **Reliability** - Always have system default fallback
3. **Flexibility** - Tenants can fully customize or use default
4. **Maintainability** - Default template updated centrally
5. **User-Friendly** - One-click load recommended fields
6. **Professional** - All tenants get beautiful payslips immediately

---

## 🎯 **Summary**

**What You Have:**
- ✅ Multi-tenant payslip designer (WORKING!)
- ✅ System default template (professional table layout)
- ✅ Per-company customization
- ✅ Fallback mechanism
- ✅ All bugs fixed (orientation, positions, checkboxes, layout)

**What You Need:**
1. Create `payroll/constants.py` with defaults
2. Create `payroll/utils.py` with helper functions
3. Update PDF generation to use `get_payslip_design()`
4. Run migration for `payslip_section_color` field
5. Create PDF templates

**Result:**
- Each tenant gets beautiful payslips immediately
- Full customization available if needed
- System-wide consistency with flexibility
- Bulletproof multi-tenant architecture

---

**Status:** ✅ Architecture Designed, Bugs Fixed, Ready for Implementation!
