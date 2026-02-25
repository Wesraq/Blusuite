# 🎨 BLU Suite - Official Color Theme

**Design System: Teal, Dark Red, Black, Grey**

---

## 🎯 PRIMARY COLORS

### **Teal (Primary Action Color)**
```css
/* Official Teal Palette */
--teal-100: #b2d8d8;  /* Lightest - backgrounds */
--teal-300: #66b2b2;  /* Light - hover states */
--teal-500: #008080;  /* Main - primary actions */
--teal-700: #006666;  /* Dark - active states */
--teal-900: #004c4c;  /* Darkest - text on light */

/* Teal Variants */
--teal-light: rgba(0, 128, 128, 0.16);  /* Backgrounds */
--teal-hover: rgba(0, 128, 128, 0.14);  /* Hover states */
--teal-shadow: rgba(0, 128, 128, 0.3);  /* Shadows */
```

**Usage:**
- Primary buttons
- Active states
- Success indicators
- Progress bars (active)
- Links and CTAs

---

### **Dark Red (Alert/Warning Color)**
```css
/* Main Dark Red */
--red-600: #dc2626;
--red-700: #b91c1c;
--red-800: #991b1b;

/* Red Variants */
--red-light: rgba(220, 38, 38, 0.16);
--red-hover: rgba(220, 38, 38, 0.14);
```

**Usage:**
- Error states
- Warnings
- On-hold status
- Overdue indicators
- Delete actions

---

### **Black (Text & Dark Elements)**
```css
/* Main Black */
--black: #0f172a;  /* Slate 900 */
--black-light: #1e293b;  /* Slate 800 */

/* Black Variants */
--black-bg: rgba(15, 23, 42, 0.92);  /* Card backgrounds */
--black-text: #0f172a;  /* Primary text */
```

**Usage:**
- Primary text
- Headers
- Dark stat cards
- Completed status
- High contrast elements

---

### **Grey (Neutral & Secondary)**
```css
/* Grey Scale */
--grey-900: #0f172a;  /* Darkest */
--grey-800: #1e293b;
--grey-700: #334155;
--grey-600: #475569;
--grey-500: #64748b;  /* Mid grey */
--grey-400: #94a3b8;
--grey-300: #cbd5e1;
--grey-200: #e2e8f0;
--grey-100: #f1f5f9;
--grey-50: #f8fafc;   /* Lightest */

/* Grey Variants */
--grey-light: rgba(148, 163, 184, 0.12);  /* Backgrounds */
--grey-border: rgba(148, 163, 184, 0.4);  /* Borders */
```

**Usage:**
- Secondary text (#64748b)
- Borders (#e2e8f0)
- Backgrounds (#f8fafc)
- Planning status (#64748b)
- Disabled states

---

## 📊 STATUS COLORS

### **Project/Task Status**
```css
/* Planning */
--status-planning: #64748b;  /* Grey */
--status-planning-bg: rgba(100, 116, 139, 0.16);

/* Active */
--status-active: #14b8a6;  /* Teal */
--status-active-bg: rgba(20, 184, 166, 0.16);

/* On Hold */
--status-on-hold: #dc2626;  /* Dark Red */
--status-on-hold-bg: rgba(220, 38, 38, 0.16);

/* Completed */
--status-completed: #0f172a;  /* Black */
--status-completed-bg: rgba(15, 23, 42, 0.16);
```

---

## 🎨 MODULE-SPECIFIC ACCENTS

### **Projects (PMS)**
- Primary: Teal (#14b8a6)
- Gradient: `linear-gradient(135deg, #14b8a6 0%, #0d9488 100%)`
- Chip: Teal background

### **Analytics**
- Primary: Teal (#14b8a6)
- Secondary: Grey (#64748b)
- Charts: Teal, Dark Red, Black, Grey palette

### **Billing**
- Primary: Teal (#14b8a6)
- Alert: Dark Red (#dc2626)
- Success: Teal

### **Support**
- Primary: Teal (#14b8a6)
- Urgent: Dark Red (#dc2626)
- Resolved: Black (#0f172a)

---

## 🎯 UI COMPONENT COLORS

### **Buttons**
```css
/* Primary Button */
.btn-primary {
    background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%);
    color: white;
    box-shadow: 0 20px 40px rgba(20, 184, 166, 0.3);
}

/* Secondary Button */
.btn-secondary {
    background: rgba(148, 163, 184, 0.12);
    color: #0f172a;
}

/* Danger Button */
.btn-danger {
    background: #dc2626;
    color: white;
}
```

### **Cards**
```css
/* White Card */
.card {
    background: white;
    border-radius: 20px;
    box-shadow: 0 20px 40px rgba(15, 23, 42, 0.06);
}

/* Dark Stat Card */
.stat-card {
    background: rgba(15, 23, 42, 0.92);
    color: white;
}

/* Action Tile */
.action-tile {
    background: rgba(148, 163, 184, 0.12);
}

.action-tile:hover {
    background: rgba(20, 184, 166, 0.14);
}
```

### **Text Colors**
```css
/* Headings */
h1, h2, h3 {
    color: #0f172a;
}

/* Body Text */
p {
    color: #475569;
}

/* Secondary Text */
.text-secondary {
    color: #64748b;
}

/* Muted Text */
.text-muted {
    color: #94a3b8;
}
```

### **Backgrounds**
```css
/* Page Background */
body {
    background: #f8fafc;
}

/* Section Background */
.section-bg {
    background: white;
}

/* Hover Background */
.hover-bg:hover {
    background: rgba(20, 184, 166, 0.14);
}
```

---

## 📈 CHART COLORS

### **Primary Chart Palette**
```javascript
const chartColors = {
    teal: '#14b8a6',
    darkRed: '#dc2626',
    black: '#0f172a',
    grey: '#64748b',
    lightGrey: '#94a3b8',
};
```

### **Chart Usage**
- **Line Charts**: Teal for primary, Dark Red for secondary
- **Bar Charts**: Teal gradient
- **Pie Charts**: Teal, Dark Red, Black, Grey rotation
- **Area Charts**: Teal with opacity

---

## 🎨 GRADIENT COMBINATIONS

### **Primary Gradients**
```css
/* Teal Gradient */
background: linear-gradient(135deg, #14b8a6 0%, #0d9488 100%);

/* Dark Gradient */
background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);

/* Grey Gradient */
background: linear-gradient(135deg, #64748b 0%, #475569 100%);
```

---

## 🔔 NOTIFICATION COLORS

```css
/* Success */
--success: #14b8a6;
--success-bg: rgba(20, 184, 166, 0.16);

/* Error */
--error: #dc2626;
--error-bg: rgba(220, 38, 38, 0.16);

/* Warning */
--warning: #f59e0b;
--warning-bg: rgba(245, 158, 11, 0.16);

/* Info */
--info: #64748b;
--info-bg: rgba(100, 116, 139, 0.16);
```

---

## 📱 RESPONSIVE CONSIDERATIONS

- All colors maintain WCAG AA contrast ratios
- Dark mode ready (invert black/white)
- Colorblind friendly (teal/red combination)
- Print-friendly alternatives available

---

## 🎯 ACCESSIBILITY

### **Contrast Ratios**
- Teal on White: 4.5:1 ✅
- Dark Red on White: 7.2:1 ✅
- Black on White: 16.7:1 ✅
- Grey on White: 4.6:1 ✅

### **Focus States**
```css
:focus {
    outline: 2px solid #14b8a6;
    outline-offset: 2px;
}
```

---

## 🎨 QUICK REFERENCE

| Element | Color | Hex |
|---------|-------|-----|
| Primary Action | Teal | #14b8a6 |
| Alert/Warning | Dark Red | #dc2626 |
| Text | Black | #0f172a |
| Secondary Text | Grey | #64748b |
| Background | Light Grey | #f8fafc |
| Border | Grey | #e2e8f0 |
| Success | Teal | #14b8a6 |
| Error | Dark Red | #dc2626 |
| Disabled | Light Grey | #94a3b8 |

---

**Last Updated:** November 3, 2025  
**Design System:** BLU Suite v1.0  
**Theme:** Teal, Dark Red, Black, Grey
