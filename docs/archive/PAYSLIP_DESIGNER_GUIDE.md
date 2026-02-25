# 📄 Payslip Designer - User Guide

**Access URL:** `http://127.0.0.1:8000/settings/payslip-designer/`

**Required Roles:** ADMINISTRATOR, EMPLOYER_ADMIN, ADMIN

---

## 🎨 **Overview**

The Payslip Designer allows you to customize your company's payslip layout using an intuitive drag-and-drop interface. Design professional payslips that match your company's branding and requirements.

---

## 🖥️ **Interface Layout**

The designer is divided into three main panels:

### **1. Left Panel - Available Sections** 📦
Contains draggable sections you can add to your payslip:
- 👤 **Employee Information** - Name, ID, department, position
- 💰 **Salary Information** - Basic salary, gross pay
- 📉 **Deductions** - Tax, insurance, loans
- ➕ **Allowances** - Housing, transport, meal allowances
- 📊 **Summary** - Net pay, total earnings, total deductions
- 🧾 **Tax Breakdown** - Detailed tax calculations
- 📅 **YTD Summary** - Year-to-date totals

### **2. Center Panel - Canvas** 🎨
The main design area where you build your payslip layout:
- Drag sections from the left panel here
- Reorder sections using ↑ ↓ buttons
- Remove sections using ✕ button
- Automatically adjusts to portrait/landscape orientation

### **3. Right Panel - Properties** ⚙️
Configure positioning and content:
- **Logo Position** - Choose from 6 positions
- **Stamp Position** - Choose from 6 positions
- **Address Position** - Choose from 6 positions
- **Header Content** - Custom header text/HTML
- **Footer Content** - Custom footer text/HTML

---

## 📋 **How to Use**

### **Step 1: Choose Orientation**
Click the orientation toggle at the top:
- 📄 **Portrait** - Standard vertical layout (8.5" × 11")
- 📃 **Landscape** - Horizontal layout (11" × 8.5")

### **Step 2: Add Sections**
1. Find the section you want in the left panel
2. Click and drag it to the center canvas
3. Drop it where you want it to appear
4. The section will be added to your payslip

### **Step 3: Arrange Sections**
- Use **↑** button to move a section up
- Use **↓** button to move a section down
- Use **✕** button to remove a section
- Sections appear on the payslip in the order shown on canvas

### **Step 4: Configure Positions**
In the right panel, click position options to set:
- **Logo Position** - Where your company logo appears
- **Stamp Position** - Where your company stamp appears
- **Address Position** - Where your company address appears

Position options:
- Top Left
- Top Center
- Top Right
- Bottom Left
- Bottom Center
- Bottom Right

### **Step 5: Customize Content**
In the right panel:
- **Header Content** - Add custom text or HTML for the payslip header
- **Footer Content** - Add disclaimers, notes, or legal text

### **Step 6: Save Your Design**
Click the **💾 Save Design** button at the top to save all changes.

---

## 💡 **Tips & Best Practices**

### **Section Order**
Recommended order for professional payslips:
1. Employee Information (top)
2. Salary Information
3. Allowances
4. Deductions
5. Tax Breakdown (optional)
6. Summary
7. YTD Summary (optional, bottom)

### **Logo & Stamp Placement**
- **Logo:** Usually top-left or top-center
- **Stamp:** Usually bottom-right
- **Address:** Usually top-right

### **Header Content Examples**
```html
<h2>Monthly Payslip</h2>
<p>Confidential Document</p>
```

### **Footer Content Examples**
```
This is a computer-generated payslip and does not require a signature.
For queries, contact HR at hr@company.com

---

CONFIDENTIAL: This document contains sensitive information.
```

---

## 🎯 **Common Use Cases**

### **Minimal Payslip**
Sections:
1. Employee Information
2. Salary Information
3. Deductions
4. Summary

### **Detailed Payslip**
Sections:
1. Employee Information
2. Salary Information
3. Allowances
4. Deductions
5. Tax Breakdown
6. Summary

### **Comprehensive Payslip**
All sections:
1. Employee Information
2. Salary Information
3. Allowances
4. Deductions
5. Tax Breakdown
6. Summary
7. YTD Summary

---

## 🔧 **Technical Details**

### **Data Storage**
Your design is saved in the database with:
- `payslip_orientation` - Portrait or landscape
- `payslip_section_order` - Array of section IDs in order
- `payslip_logo_position` - Logo position string
- `payslip_stamp_position` - Stamp position string
- `payslip_address_position` - Address position string
- `payslip_header_content` - Custom header text/HTML
- `payslip_footer_content` - Custom footer text/HTML
- `payslip_field_positions` - JSON object for custom field positions

### **Section IDs**
- `employee_info` - Employee Information
- `salary_info` - Salary Information
- `deductions` - Deductions
- `allowances` - Allowances
- `summary` - Summary
- `tax_breakdown` - Tax Breakdown
- `ytd_summary` - YTD Summary

### **Position Values**
- `top-left`
- `top-center`
- `top-right`
- `bottom-left`
- `bottom-center`
- `bottom-right`

---

## 🚀 **Future Enhancements**

The following features are planned for future releases:

1. **Live Preview** - See actual payslip with sample data
2. **Field-Level Customization** - Drag individual fields within sections
3. **Multiple Templates** - Save and switch between different designs
4. **Template Library** - Pre-designed templates to choose from
5. **Export Templates** - Share designs with other companies
6. **Custom Sections** - Create your own custom sections
7. **Conditional Display** - Show/hide sections based on conditions
8. **Color Customization** - Per-section color schemes
9. **Font Customization** - Choose fonts and sizes
10. **Watermark Support** - Add watermarks to payslips

---

## ❓ **Troubleshooting**

### **Section won't drag**
- Make sure you're clicking and holding on the section item
- Try refreshing the page
- Check browser console for JavaScript errors

### **Changes not saving**
- Click the "Save Design" button after making changes
- Check that you have the required permissions
- Verify you're logged in as ADMINISTRATOR, EMPLOYER_ADMIN, or ADMIN

### **Canvas looks wrong**
- Try switching orientation and back
- Clear browser cache
- Try a different browser

### **Section appears twice**
- Each section can only be added once
- Remove the section and add it again if needed

---

## 📞 **Support**

For assistance with the Payslip Designer:
1. Check this guide for common solutions
2. Contact your system administrator
3. Check the browser console for error messages
4. Verify all migrations are applied: `python manage.py migrate`

---

## 📝 **Changelog**

### **Version 1.0 - October 10, 2025**
- ✅ Initial release
- ✅ Drag-and-drop interface
- ✅ 7 available sections
- ✅ Portrait/landscape orientation
- ✅ Logo, stamp, address positioning
- ✅ Custom header/footer content
- ✅ Section reordering
- ✅ Responsive design

---

**Last Updated:** October 10, 2025  
**Version:** 1.0  
**Status:** Production Ready ✅
