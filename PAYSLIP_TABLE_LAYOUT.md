# 📋 Professional Table Layout Payslip - Implementation Guide

## ✅ **What's Been Implemented**

### **1. Pre-Designed "Professional Table Layout" Template**

**Location:** Right sidebar → "Payslip Layout Style" dropdown

**Features:**
- ⭐ **Professional Table Layout (Recommended)** - Matches MFI payslip design
- Logo Left, Address Right
- Logo Center, Info Below
- Logo Right, Address Left
- Modern Gradient Header

### **2. One-Click Field Loading**

**Button:** 📋 "Load Recommended Fields"

**Auto-loads these fields in order:**
1. Employee Name
2. Employee ID
3. Position
4. Department
5. Pay Period
6. Basic Salary
7. Housing Allowance
8. Transport Allowance
9. Other Allowances
10. Gross Pay
11. NAPSA
12. NHIMA
13. PAYE
14. Loans
15. Advances
16. Total Allowances
17. Total Deductions
18. **Net Pay**

**This matches the MFI payslip structure perfectly!**

### **3. Section Header Color Picker**

**New Setting:** "Section Headers" color picker

**Default:** #C5D9F1 (Light Blue - matches your image)

**What it controls:**
- EARNINGS section header
- STATUTORY DEDUCTION section header
- OTHER DEDUCTIONS section header
- Any other section headers

### **4. Backend Updates**

**New field saved:** `company.payslip_section_color`

**Updated in:** `frontend_views.py` (line 2517)
```python
company.payslip_section_color = request.POST.get('payslip_section_color', '#C5D9F1')
```

---

## 🎨 **Design Specifications from Your Image**

### **Header Section:**
```
┌─────────────────────────────────────────────────┐
│ [LOGO]          MFI DOCUMENT SOLUTION LIMITED   │
│                 1193 Lunzua Road, Off Addis...  │
│                 P.O.Box 31665                   │
│                 Lusaka, Zambia                  │
└─────────────────────────────────────────────────┘
```

### **Employee Info Table:**
```
┌──────────────────────┬──────────────────────────┐
│  Employee Name :     │ EMMANUEL SIMWANZA        │
│  Employee ID :       │ MFI031                   │
│  Designation :       │ IT ASSISTANT             │
│  Department :        │ IT-TELECOMS              │
│  NRC :              │ 431449/10/1              │
│  Month :            │ Oct-2025                 │
└──────────────────────┴──────────────────────────┘
```

### **Earnings Section:**
```
┌─────────────────────────────────────────────────┐
│              EARNINGS               (Blue BG)   │
├──────────────────────────────┬──────────────────┤
│ Basic Salary                 │ ZMW 12.00        │
│ House Rents Allowance (@30%) │ ZMW 3.60         │
│ Transport Allowance          │ ZMW 180.00       │
│ Lunch Allowance              │ ZMW 200.00       │
│ Gross Salary                 │ ZMW 395.60       │
└──────────────────────────────┴──────────────────┘
```

### **Statutory Deductions Section:**
```
┌─────────────────────────────────────────────────┐
│         STATUTORY DEDUCTION         (Blue BG)   │
├──────────────────────────────┬──────────────────┤
│ NAPSA @5%                    │ ZMW 19.78        │
│ NHIMA                        │ ZMW 2.77         │
│ PAYE                         │ ZMW 0.00         │
└──────────────────────────────┴──────────────────┘
```

### **Other Deductions Section:**
```
┌─────────────────────────────────────────────────┐
│           OTHER DEDUCTIONS          (Blue BG)   │
├──────────────────────────────┬──────────────────┤
│ Late Deductions              │ ZMW 0.00 (RED)   │
│ Salary Advance               │ ZMW 0.00 (RED)   │
│ Loans                        │ ZMW 0.00 (RED)   │
└──────────────────────────────┴──────────────────┘
```

### **Totals Section:**
```
┌──────────────────────────────┬──────────────────┐
│ Total Earnings (A)           │ ZMW 395.60       │
│ Total Deductions (B)         │ ZMW 22.55        │
│ GRATUITY + BONUS             │ -                │
│ Net Salary (A-B)             │ ZMW 373.05 BOLD  │
│ NET PAY BALANCE              │ -                │
└──────────────────────────────┴──────────────────┘
```

### **Footer Section:**
```
┌─────────────────────────────────────────────────┐
│ Reciever's Name: Emmanuel Simwanza              │
│                                     [STAMP]     │
│ Company Stamp                                   │
│                                                 │
│ Pay Slip Not Valid Unless Stamped              │
│ Please Treat Your Pay Slip as Confidential.    │
│                Have a Nice Month                │
└─────────────────────────────────────────────────┘
```

---

## 🔧 **Next Steps: PDF Generation**

### **Phase 1: Update Company Model (Database)**

**Need to add field:**
```python
# In accounts/models.py - Company model
payslip_section_color = models.CharField(max_length=7, default='#C5D9F1', blank=True)
```

**Migration needed:**
```bash
python manage.py makemigrations
python manage.py migrate
```

### **Phase 2: Create Payslip Template**

**Create:** `templates/payroll/payslip_professional_table.html`

**Structure:**
```html
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body { font-family: Arial, sans-serif; font-size: 11pt; }
        .header { 
            display: flex; 
            justify-content: space-between; 
            border-bottom: 2px solid #000; 
            padding-bottom: 10px;
        }
        .logo { max-width: 150px; }
        .company-info { text-align: right; }
        
        .employee-table {
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }
        .employee-table td {
            padding: 4px 8px;
            border: 1px solid #000;
        }
        .employee-table td:first-child {
            text-align: right;
            font-weight: 500;
            width: 40%;
        }
        
        .section-header {
            background-color: {{ company.payslip_section_color }};
            font-weight: bold;
            text-align: center;
            padding: 6px;
            border: 1px solid #000;
            text-transform: uppercase;
        }
        
        .amount-table {
            width: 100%;
            border-collapse: collapse;
        }
        .amount-table td {
            padding: 4px 8px;
            border: 1px solid #000;
        }
        .amount-table td:last-child {
            text-align: right;
            font-family: monospace;
        }
        
        .red-amount { color: #ff0000; }
        .bold-total { font-weight: bold; font-size: 14pt; }
        
        .footer {
            margin-top: 20px;
            border-top: 2px solid #000;
            padding-top: 10px;
        }
        .stamp-area {
            text-align: right;
            margin: 10px 0;
        }
        .confidential {
            text-align: center;
            font-size: 9pt;
            color: #666;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <!-- HEADER -->
    <div class="header">
        <div>
            {% if company.logo %}
            <img src="{{ company.logo.url }}" class="logo" alt="Logo">
            {% endif %}
            <div style="font-size: 9pt; margin-top: 5px;">Your Ambition Our Mission</div>
        </div>
        <div class="company-info">
            <div style="font-weight: bold; font-size: 14pt;">{{ company.name|upper }}</div>
            <div>{{ company.address }}</div>
            <div>P.O.Box {{ company.po_box|default:"XXXXX" }}</div>
            <div>{{ company.city }}, Zambia</div>
        </div>
    </div>
    
    <!-- EMPLOYEE INFO -->
    <table class="employee-table">
        <tr>
            <td>Employee Name :</td>
            <td>{{ employee.full_name|upper }}</td>
        </tr>
        <tr>
            <td>Employee ID :</td>
            <td>{{ employee.employee_id }}</td>
        </tr>
        <tr>
            <td>Designation :</td>
            <td>{{ employee.position|upper }}</td>
        </tr>
        <tr>
            <td>Department :</td>
            <td>{{ employee.department|upper }}</td>
        </tr>
        <tr>
            <td>NRC :</td>
            <td>{{ employee.nrc|default:"-" }}</td>
        </tr>
        <tr>
            <td>Month :</td>
            <td>{{ payroll.period }}</td>
        </tr>
    </table>
    
    <!-- EARNINGS -->
    <div class="section-header">EARNINGS</div>
    <table class="amount-table">
        <tr>
            <td>Basic Salary</td>
            <td>ZMW {{ payroll.basic_salary|floatformat:2 }}</td>
        </tr>
        {% if payroll.housing_allowance > 0 %}
        <tr>
            <td>House Rents Allowance (@30%)</td>
            <td>ZMW {{ payroll.housing_allowance|floatformat:2 }}</td>
        </tr>
        {% endif %}
        {% if payroll.transport_allowance > 0 %}
        <tr>
            <td>Transport Allowance</td>
            <td>ZMW {{ payroll.transport_allowance|floatformat:2 }}</td>
        </tr>
        {% endif %}
        {% if payroll.other_allowances > 0 %}
        <tr>
            <td>Lunch Allowance</td>
            <td>ZMW {{ payroll.other_allowances|floatformat:2 }}</td>
        </tr>
        {% endif %}
        <tr>
            <td><strong>Gross Salary</strong></td>
            <td><strong>ZMW {{ payroll.gross_pay|floatformat:2 }}</strong></td>
        </tr>
    </table>
    
    <!-- STATUTORY DEDUCTIONS -->
    <div class="section-header" style="margin-top: 10px;">STATUTORY DEDUCTION</div>
    <table class="amount-table">
        <tr>
            <td>NAPSA @5%</td>
            <td>ZMW {{ payroll.napsa|floatformat:2 }}</td>
        </tr>
        <tr>
            <td>NHIMA</td>
            <td>ZMW {{ payroll.nhima|floatformat:2 }}</td>
        </tr>
        <tr>
            <td>PAYE</td>
            <td {% if payroll.paye == 0 %}class="red-amount"{% endif %}>
                ZMW {{ payroll.paye|floatformat:2 }}
            </td>
        </tr>
    </table>
    
    <!-- OTHER DEDUCTIONS -->
    <div class="section-header" style="margin-top: 10px;">OTHER DEDUCTIONS</div>
    <table class="amount-table">
        <tr>
            <td>Late Deductions</td>
            <td class="red-amount">ZMW 0.00</td>
        </tr>
        <tr>
            <td>Salary Advance</td>
            <td {% if payroll.advances == 0 %}class="red-amount"{% endif %}>
                ZMW {{ payroll.advances|floatformat:2 }}
            </td>
        </tr>
        <tr>
            <td>Loans</td>
            <td {% if payroll.loans == 0 %}class="red-amount"{% endif %}>
                ZMW {{ payroll.loans|floatformat:2 }}
            </td>
        </tr>
    </table>
    
    <!-- TOTALS -->
    <table class="amount-table" style="margin-top: 10px;">
        <tr>
            <td>Total Earnings (A)</td>
            <td>ZMW {{ payroll.gross_pay|floatformat:2 }}</td>
        </tr>
        <tr>
            <td>Total Deductions (B)</td>
            <td>ZMW {{ payroll.total_deductions|floatformat:2 }}</td>
        </tr>
        <tr>
            <td>GRATUITY + BONUS</td>
            <td>-</td>
        </tr>
        <tr>
            <td class="bold-total">Net Salary (A-B)</td>
            <td class="bold-total">ZMW {{ payroll.net_pay|floatformat:2 }}</td>
        </tr>
        <tr>
            <td>NET PAY BALANCE</td>
            <td>-</td>
        </tr>
    </table>
    
    <!-- FOOTER -->
    <div class="footer">
        <div>Reciever's Name: <strong>{{ employee.full_name }}</strong></div>
        
        <div class="stamp-area">
            {% if company.company_stamp %}
            <img src="{{ company.company_stamp.url }}" style="max-height: 80px;" alt="Stamp">
            {% endif %}
            <div style="margin-top: 5px;">Company Stamp</div>
        </div>
        
        <div class="confidential">
            <div style="font-weight: bold; margin-bottom: 5px;">
                Pay Slip Not Valid Unless Stamped
            </div>
            <div>{{ company.payslip_footer_text|default:"Please Treat Your Pay Slip as Confidential. Have a Nice Month" }}</div>
        </div>
        
        <div style="font-size: 8pt; color: #ff0000; margin-top: 10px;">
            *Payslip System generated
        </div>
        
        <div style="text-align: center; margin-top: 15px; padding-top: 10px; border-top: 1px solid #000; font-size: 9pt;">
            <div style="font-weight: bold;">{{ company.name|upper }}</div>
            <div>Head Office: No. 16, Kambule Road, Off James Chinula Road, P.O Box 4532 – 00200, Nairobi, Kenya</div>
            <div>Kenya: (020) 2347840, Fax: 254 - 20 - 3241690, E-mail: headoffice@groupmail.com</div>
            <div style="margin-top: 5px; font-weight: bold;">
                KENYA - UGANDA - TANZANIA - RWANDA - ETHIOPIA - NIGERIA - ZAMBIA
            </div>
        </div>
    </div>
</body>
</html>
```

### **Phase 3: Create PDF Generator View**

**Create:** `payroll/views.py` (or update existing)

```python
from django.template.loader import render_to_string
from weasyprint import HTML
from django.http import HttpResponse

def generate_payslip_pdf(request, payroll_id):
    payroll = get_object_or_404(Payroll, id=payroll_id)
    employee = payroll.employee
    company = payroll.company
    
    # Choose template based on layout style
    if company.payslip_header_style == 'professional_table':
        template = 'payroll/payslip_professional_table.html'
    else:
        template = 'payroll/payslip_default.html'
    
    # Render HTML
    html_string = render_to_string(template, {
        'payroll': payroll,
        'employee': employee,
        'company': company,
    })
    
    # Generate PDF
    html = HTML(string=html_string)
    pdf = html.write_pdf()
    
    # Return as response
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="payslip_{employee.employee_id}_{payroll.period}.pdf"'
    
    return response
```

---

## 📋 **Testing Workflow**

### **Step 1: Design Phase**
1. Go to Settings → Company Settings
2. Click "Payslip Designer" tab
3. Select "⭐ Professional Table Layout"
4. Click "📋 Load Recommended Fields"
5. Adjust section header color (default #C5D9F1 is perfect)
6. Set header/footer text
7. Click "Save Design"

### **Step 2: Generation Phase**
1. Process payroll for employee
2. Go to payroll list
3. Click "Generate Payslip" button
4. System loads `professional_table` template
5. Populates all fields from database
6. Applies colors (header, section, etc.)
7. Generates PDF

### **Step 3: Output**
- PDF matches MFI payslip design
- Logo and stamp auto-included
- Blue section headers
- Right-aligned amounts with "ZMW"
- Red zeros for deductions
- Bold net salary
- Professional footer

---

## ✅ **Current Status**

**✅ Designer Interface:** Complete  
**✅ Field Selection:** Complete  
**✅ One-Click Load:** Complete  
**✅ Color Customization:** Complete  
**✅ Backend Saving:** Complete  
**⏳ Database Migration:** Need to add `payslip_section_color` field  
**⏳ PDF Template:** Need to create `payslip_professional_table.html`  
**⏳ PDF Generator:** Need to integrate with payroll system  

---

## 🎯 **Summary**

**What You Have Now:**
- Beautiful designer interface
- One-click template loading (18 recommended fields)
- Full customization (colors, layout, fields)
- Tab persistence (no more jumping to profile)
- Live preview with logo/stamp
- Individual field selection

**What's Needed:**
1. Run migration to add `payslip_section_color` field
2. Create professional table HTML template
3. Integrate with payroll PDF generator
4. Test with real data

**Result:**
Perfect MFI-style payslips matching your image! 🎉
