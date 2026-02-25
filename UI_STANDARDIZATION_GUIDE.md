# UI Standardization Guide - BLU Suite EMS

**Created:** January 18, 2026  
**Purpose:** Standardize UI/UX across all pages to match the modern dashboard design

---

## 🎨 Design System

### **Color Palette**
```css
Primary (Teal): #008080
Primary Dark: #006666
Primary Light: #66b2b2
Primary Gradient: linear-gradient(135deg, #008080 0%, #006666 100%)

Background: #f8fafc
White: #ffffff
Border: #e2e8f0

Text Primary: #0f172a
Text Secondary: #64748b
Text Muted: #94a3b8

Success: #065f46 / #d1fae5
Warning: #d97706 / #fef3c7
Error: #dc2626 / #fecaca
Info: #1d4ed8 / #dbeafe
```

### **Typography**
```css
Headings:
- H1: 28px, 700 weight, #0f172a
- H2: 24px, 700 weight, #0f172a
- H3: 18px, 600 weight, #0f172a

Body:
- Regular: 14px, 400 weight, #0f172a
- Small: 13px, 400 weight, #64748b
- Tiny: 12px, 400 weight, #64748b
```

### **Spacing**
```css
Gap Small: 8px
Gap Medium: 12px
Gap Large: 16px
Gap XLarge: 20px
Gap XXLarge: 24px

Padding Card: 20px
Padding Button: 10px 16px
Border Radius: 8px (buttons), 12px (cards)
```

---

## 📦 Component Library

### **1. Stat Card**
```html
<div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px;">
    <div style="font-size: 14px; color: #64748b; margin-bottom: 8px;">Label</div>
    <div style="font-size: 32px; font-weight: 700; color: #0f172a; margin-bottom: 4px;">Value</div>
    <div style="font-size: 12px; color: #64748b;">Subtitle</div>
</div>
```

### **2. Gradient Stat Card (Featured)**
```html
<div style="background: linear-gradient(135deg, #008080 0%, #006666 100%); border-radius: 12px; padding: 20px; color: white; box-shadow: 0 4px 12px rgba(0, 128, 128, 0.2);">
    <div style="font-size: 14px; opacity: 0.9; margin-bottom: 8px;">Label</div>
    <div style="font-size: 32px; font-weight: 700; margin-bottom: 8px;">Value</div>
    <div style="background: rgba(255,255,255,0.2); height: 6px; border-radius: 999px; overflow: hidden;">
        <div style="background: white; height: 100%; width: 75%;"></div>
    </div>
</div>
```

### **3. Quick Action Card**
```html
<a href="#" class="quick-action-card" style="display: flex; flex-direction: column; align-items: center; padding: 16px; background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; text-decoration: none; transition: all 0.2s ease;">
    <svg width="32" height="32" fill="#008080" style="margin-bottom: 8px;">
        <!-- Icon SVG -->
    </svg>
    <div style="font-size: 13px; font-weight: 600; color: #0f172a; text-align: center;">Action Name</div>
</a>
```

### **4. Content Card**
```html
<div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px;">
    <h3 style="margin: 0 0 16px 0; color: #0f172a; font-size: 18px; font-weight: 600;">Card Title</h3>
    <!-- Content -->
</div>
```

### **5. Button Primary**
```html
<button class="btn" style="padding: 10px 16px; background: #008080; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s ease;">
    Button Text
</button>
```

### **6. Button Secondary**
```html
<button class="btn btn-secondary" style="padding: 10px 16px; background: white; color: #0f172a; border: 1px solid #e2e8f0; border-radius: 8px; font-weight: 600; cursor: pointer; transition: all 0.2s ease;">
    Button Text
</button>
```

### **7. Badge**
```html
<!-- Success Badge -->
<span style="display: inline-block; padding: 4px 12px; background: #d1fae5; color: #065f46; border-radius: 12px; font-size: 12px; font-weight: 600;">
    Active
</span>

<!-- Warning Badge -->
<span style="display: inline-block; padding: 4px 12px; background: #fef3c7; color: #d97706; border-radius: 12px; font-size: 12px; font-weight: 600;">
    Pending
</span>

<!-- Error Badge -->
<span style="display: inline-block; padding: 4px 12px; background: #fecaca; color: #dc2626; border-radius: 12px; font-size: 12px; font-weight: 600;">
    Rejected
</span>
```

### **8. Tab Navigation**
```html
<div class="tab-nav" style="display: flex; gap: 8px; border-bottom: 2px solid #e2e8f0; margin-bottom: 24px;">
    <button class="tab-btn active" style="padding: 12px 20px; background: none; border: none; border-bottom: 2px solid #008080; color: #008080; font-weight: 600; cursor: pointer;">
        Active Tab
    </button>
    <button class="tab-btn" style="padding: 12px 20px; background: none; border: none; border-bottom: 2px solid transparent; color: #64748b; font-weight: 600; cursor: pointer;">
        Inactive Tab
    </button>
</div>
```

### **9. SVG Icons (Lucide Style)**
```html
<!-- Document Icon -->
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
    <polyline points="14 2 14 8 20 8"></polyline>
</svg>

<!-- Calendar Icon -->
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect>
    <line x1="16" y1="2" x2="16" y2="6"></line>
    <line x1="8" y1="2" x2="8" y2="6"></line>
    <line x1="3" y1="10" x2="21" y2="10"></line>
</svg>

<!-- Check Icon -->
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
    <polyline points="22 4 12 14.01 9 11.01"></polyline>
</svg>

<!-- X Icon -->
<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"></line>
    <line x1="6" y1="6" x2="18" y2="18"></line>
</svg>
```

### **10. Table Row (Modern)**
```html
<div style="display: grid; grid-template-columns: 1fr 1fr 1fr 1fr auto; gap: 16px; padding: 16px; background: white; border: 1px solid #e2e8f0; border-radius: 8px; margin-bottom: 8px; align-items: center;">
    <div>
        <div style="font-weight: 600; color: #0f172a; margin-bottom: 4px;">Primary Text</div>
        <div style="font-size: 12px; color: #64748b;">Secondary Text</div>
    </div>
    <div style="font-size: 14px; color: #0f172a;">Column 2</div>
    <div style="font-size: 14px; color: #0f172a;">Column 3</div>
    <div>
        <span style="padding: 4px 12px; background: #d1fae5; color: #065f46; border-radius: 12px; font-size: 12px; font-weight: 600;">
            Status
        </span>
    </div>
    <div style="display: flex; gap: 8px;">
        <button style="padding: 6px 12px; background: #008080; color: white; border: none; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer;">
            Action
        </button>
    </div>
</div>
```

---

## 🎯 Pages to Update

### **Priority 1 (High Traffic)**
1. ✅ Employee Dashboard (Reference)
2. ⏳ Training List
3. ⏳ Benefits List
4. ⏳ Documents List
5. ⏳ Leave Management
6. ⏳ Attendance Dashboard

### **Priority 2 (Medium Traffic)**
7. ⏳ Performance Reviews
8. ⏳ Onboarding List
9. ⏳ Payroll List
10. ⏳ Employee Requests

### **Priority 3 (Lower Traffic)**
11. ⏳ Announcements List
12. ⏳ HR Analytics
13. ⏳ Reports Center

---

## ✅ Checklist for Each Page

- [ ] Replace emoji icons with SVG icons
- [ ] Update stat cards to use standard design
- [ ] Apply consistent card styling (border-radius: 12px, border: 1px solid #e2e8f0)
- [ ] Update buttons to use standard styles
- [ ] Replace old table layouts with modern grid/card layouts
- [ ] Add hover effects on interactive elements
- [ ] Use consistent color palette
- [ ] Apply consistent spacing (gaps, padding, margins)
- [ ] Update badges to use standard styles
- [ ] Add tab navigation where applicable
- [ ] Ensure responsive grid layouts
- [ ] Add loading states where applicable

---

## 🚀 Implementation Strategy

1. **Create reusable CSS classes** in base template
2. **Update templates one by one** starting with Priority 1
3. **Test each page** after updates
4. **Document any custom components** needed
5. **Get user feedback** after each batch

---

**Status:** In Progress  
**Next Steps:** Begin with Training List template
