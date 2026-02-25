# Notifications Integration Guide

This document outlines all in-app notifications integrated across different modules in the EMS system.

## Overview

The system now creates **in-app notifications** in addition to email notifications for all major workflow events. Notifications appear in the bell icon and on the Notifications page.

---

## 📋 Integrated Modules

### ✅ 1. Contract Management Module

**Location:** `blu_staff/apps/contracts/views.py`

#### Notifications Created:

**A. Contract Renewal Submitted (for Approval)**
- **Recipient:** All Admins/Directors
- **Sender:** HR who submitted
- **Type:** INFO (Blue)
- **Title:** "New Contract Renewal Request"
- **Message:** Employee name, job title, proposed start date
- **Action URL:** `/contracts/renewals/`
- **Trigger:** When HR clicks "Submit for Approval"

**B. Contract Renewal Approved**
- **Recipients:** 
  - HR who submitted the request
  - Employee whose contract was renewed
- **Sender:** Admin who approved
- **Type:** SUCCESS (Green)
- **Titles:** 
  - "Contract Renewal Approved" (to HR)
  - "Your Contract Has Been Renewed" (to Employee)
- **Action URL:** Link to new contract details
- **Trigger:** When Admin approves renewal request

**C. Contract Renewal Rejected**
- **Recipient:** HR who submitted
- **Sender:** Admin who rejected
- **Type:** WARNING (Yellow)
- **Title:** "Contract Renewal Rejected"
- **Message:** Includes rejection reason
- **Action URL:** `/contracts/renewals/`
- **Trigger:** When Admin rejects renewal request

**D. Direct Contract Renewal (Renew Now)**
- **Recipient:** Employee
- **Sender:** HR/Admin who renewed
- **Type:** SUCCESS (Green)
- **Title:** "Your Contract Has Been Renewed"
- **Message:** Contract number and start date
- **Action URL:** Link to new contract
- **Trigger:** When using "Renew Contract Now" button

---

### ✅ 2. Leave Management Module

**Location:** `ems_project/frontend_views.py`

#### Notifications Created:

**A. Leave Request Submitted**
- **Recipient:** All Admins and HR staff
- **Sender:** Employee who submitted
- **Type:** INFO (Blue)
- **Title:** "New Leave Request"
- **Message:** Employee name, leave type, dates
- **Action URL:** `/approval-center/`
- **Trigger:** When employee submits leave request

**B. Leave Request Approved**
- **Recipient:** Employee who submitted
- **Sender:** Admin/HR who approved
- **Type:** SUCCESS (Green)
- **Title:** "Leave Request Approved"
- **Message:** Leave type and dates
- **Action URL:** `/leave/`
- **Trigger:** When Admin/HR approves leave

**C. Leave Request Rejected**
- **Recipient:** Employee who submitted
- **Sender:** Admin/HR who rejected
- **Type:** WARNING (Yellow)
- **Title:** "Leave Request Rejected"
- **Message:** Leave type, dates, and rejection reason
- **Action URL:** `/leave/`
- **Trigger:** When Admin/HR rejects leave

---

## 🔔 Notification Types

The system uses three notification types:

| Type | Color | Icon | Use Case |
|------|-------|------|----------|
| **INFO** | Blue | ℹ️ | New requests, general information |
| **SUCCESS** | Green | ✅ | Approvals, completed actions |
| **WARNING** | Yellow | ⚠️ | Rejections, alerts |

---

## 📱 Notification Categories

Notifications are categorized for easy filtering:

- `contract_renewal` - Contract renewal workflows
- `contract` - General contract notifications
- `leave` - Leave/time-off requests
- `payroll` - Payroll notifications (pending)
- `performance` - Performance reviews (pending)
- `training` - Training assignments (pending)
- `onboarding` - Onboarding tasks (pending)
- `document` - Document approvals (pending)

---

## 🎯 Pending Integrations

The following modules still need in-app notification integration:

### 3. Payroll Module
- [ ] Payslip generated
- [ ] Payroll processed
- [ ] Payment confirmation

### 4. Performance Review Module
- [ ] Review assigned
- [ ] Review submitted
- [ ] Review completed
- [ ] Feedback received

### 5. Training Module
- [ ] Training assigned
- [ ] Training completed
- [ ] Certificate issued
- [ ] Training reminder

### 6. Onboarding Module
- [ ] New employee onboarding started
- [ ] Task assigned
- [ ] Task completed
- [ ] Onboarding completed

### 7. Document Management
- [ ] Document uploaded
- [ ] Document approval requested
- [ ] Document approved/rejected
- [ ] Document expiring soon

### 8. Attendance Module
- [ ] Late check-in alert
- [ ] Missing check-out reminder
- [ ] Attendance anomaly detected

---

## 💻 Implementation Pattern

All notifications follow this standard pattern:

```python
from blu_staff.apps.notifications.models import Notification

# Create notification
Notification.objects.create(
    recipient=user_object,           # User who receives notification
    sender=request.user,              # User who triggered action
    title='Notification Title',       # Short title
    message='Detailed message',       # Full message
    notification_type='SUCCESS',      # INFO, SUCCESS, or WARNING
    category='module_name',           # Module category
    action_url='/path/to/action/',   # Where to go when clicked
)
```

---

## 📧 Email + In-App Notifications

The system sends **both**:

1. **Email Notification** - Sent to user's email address
2. **In-App Notification** - Visible in the notifications page

This ensures users are notified even if they're not logged in, while also providing a centralized notification center within the app.

---

## 🔗 Notification Links

All notifications include action URLs that direct users to relevant pages:

- Contract notifications → Contract details page
- Leave notifications → Leave management page
- Approval notifications → Approval center
- General notifications → Module dashboard

---

## ✅ Benefits

1. **Centralized Communication** - All notifications in one place
2. **Real-time Updates** - Users see notifications immediately
3. **Audit Trail** - Complete history of all notifications
4. **Better UX** - Users don't need to check email constantly
5. **Actionable** - Click to go directly to relevant page

---

## 🧪 Testing Notifications

To test notifications:

1. **Contract Renewals:**
   - Submit a renewal request → Admin gets notification
   - Approve/reject → HR and employee get notifications
   - Use "Renew Now" → Employee gets notification

2. **Leave Requests:**
   - Submit leave → Admin/HR get notifications
   - Approve leave → Employee gets notification
   - Reject leave → Employee gets notification with reason

3. **Check Notifications Page:**
   - Click bell icon in header
   - Go to Notifications page
   - Filter by category or type
   - Click notification to go to action page

---

## 📊 Notification Statistics

Current integration status:

- ✅ **Contract Management:** 4 notification types
- ✅ **Leave Management:** 3 notification types
- ⏳ **Payroll:** Pending
- ⏳ **Performance:** Pending
- ⏳ **Training:** Pending
- ⏳ **Onboarding:** Pending
- ⏳ **Documents:** Pending
- ⏳ **Attendance:** Pending

**Total Active:** 7 notification types across 2 modules

---

## 🔄 Future Enhancements

Planned improvements:

1. Push notifications (browser)
2. SMS notifications integration
3. Notification preferences per user
4. Notification grouping/batching
5. Read/unread status tracking
6. Notification scheduling
7. Digest emails (daily/weekly summary)

---

## 📝 Notes

- All notifications are tenant-scoped (multi-tenant safe)
- Notifications are created even if email sending fails
- Failed email sends don't block the main workflow
- Notifications include sender information for audit trail
- Action URLs are relative paths (work across domains)

---

**Last Updated:** February 24, 2026  
**Version:** 1.0  
**Status:** Active Development
