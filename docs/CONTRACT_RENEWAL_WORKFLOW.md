# Contract Renewal Workflow - Option B

## Overview
The contract renewal process follows an **HR-initiated workflow** where HR staff initiate renewal requests that require approval from senior management (Admin/Director) before the new contract is created.

---

## Workflow Steps

### **Step 1: HR Initiates Renewal**

**Who:** HR Staff / HR Manager

**Actions:**
1. Navigate to **Contracts** → **Expiring Contracts** or **Contract List**
2. Select an employee's contract that needs renewal
3. Click **"Renew Contract"** button
4. Fill in renewal details:
   - New start date (usually day after current contract ends)
   - New end date (or leave blank for permanent)
   - Proposed salary (optional - for salary adjustments)
   - Proposed job title (optional - for promotions)
   - Renewal notes (reason for renewal, performance notes, etc.)
   - Updated terms & conditions (if any changes)
5. Click **"Submit Renewal Request"**

**Result:** Renewal request is created with status **PENDING**

---

### **Step 2: Admin/Director Reviews & Approves**

**Who:** Administrator / Director / Employer Admin

**Actions:**
1. Receive notification about pending renewal request
2. Navigate to **Contracts** → **Renewal Requests** (pending approvals)
3. Review renewal details:
   - Employee information
   - Current contract terms
   - Proposed new terms
   - HR's renewal notes
   - Salary changes (if any)
4. Make decision:
   - **Approve:** Contract renewal is accepted
   - **Reject:** Provide rejection reason

**Result:** 
- If **Approved**: Status changes to **APPROVED**, proceeds to Step 3
- If **Rejected**: Status changes to **REJECTED**, HR is notified

---

### **Step 3: New Contract Created**

**Who:** System (Automatic)

**Actions:**
1. System automatically creates new contract with:
   - Employee: Same as original contract
   - Start Date: Proposed start date from renewal request
   - End Date: Proposed end date (or null for permanent)
   - Salary: New salary (if changed) or original salary
   - Job Title: New title (if changed) or original title
   - Terms: Updated terms or original terms
   - Status: **ACTIVE**
2. Original contract status updated to **EXPIRED** or **RENEWED**
3. Renewal request status updated to **COMPLETED**

**Result:** New contract is active and ready

---

## Permissions & Access

### **HR Staff**
- ✅ Can initiate renewal requests
- ✅ Can view all contracts
- ✅ Can view renewal request status
- ❌ Cannot approve renewal requests

### **Admin/Director**
- ✅ Can approve/reject renewal requests
- ✅ Can view all contracts and renewals
- ✅ Can override renewal decisions
- ✅ Can manually create contracts

### **Employees**
- ✅ Can view their own contract
- ❌ Cannot initiate renewal requests
- ❌ Cannot view other employees' contracts

---

## Notifications

### **When HR Submits Renewal:**
- **Admin/Director receives:** "New contract renewal request for [Employee Name] requires your approval"

### **When Admin Approves:**
- **HR receives:** "Contract renewal for [Employee Name] has been approved"
- **Employee receives:** "Your contract has been renewed until [End Date]"

### **When Admin Rejects:**
- **HR receives:** "Contract renewal for [Employee Name] was rejected. Reason: [Rejection Reason]"

---

## Expiring Contract Alerts

The system automatically monitors contract expiry dates and sends alerts:

- **60 days before expiry:** Warning notification to HR
- **30 days before expiry:** Urgent notification to HR and Admin
- **7 days before expiry:** Critical notification to HR, Admin, and Employee

---

## Key Features

### **Approval Levels**
- HR initiates (cannot self-approve)
- Admin/Director approves (higher authority)
- Clear separation of duties

### **Audit Trail**
- Who initiated the renewal
- When it was initiated
- Who approved/rejected
- When it was approved/rejected
- All changes are logged

### **Auto-Contract Creation**
- No manual contract creation needed
- System creates contract upon approval
- All data transferred from renewal request
- Original contract marked as renewed

---

## Example Scenario

**Scenario:** James Chabinga's contract expires on March 31, 2026

1. **Feb 1, 2026:** System sends alert to HR - "James Chabinga's contract expires in 60 days"

2. **Feb 15, 2026:** HR (Sarah) initiates renewal:
   - New Start: April 1, 2026
   - New End: March 31, 2027 (1-year renewal)
   - Salary: ZMW 15,000 → ZMW 16,500 (10% increase)
   - Notes: "Excellent performance, recommending salary increase"

3. **Feb 16, 2026:** Admin (Director) receives notification

4. **Feb 17, 2026:** Director reviews and approves renewal

5. **Feb 17, 2026:** System automatically:
   - Creates new contract (CONT-2026-0045)
   - Marks old contract as RENEWED
   - Sends confirmation to HR and James

6. **April 1, 2026:** New contract becomes active

---

## Troubleshooting

### **Q: What if renewal is rejected?**
**A:** HR can submit a new renewal request with adjusted terms, or discuss with the Director.

### **Q: Can a renewal be cancelled after submission?**
**A:** Yes, HR or Admin can cancel pending renewal requests before approval.

### **Q: What happens to the old contract?**
**A:** The old contract status changes to "RENEWED" and remains in the system for record-keeping.

### **Q: Can we renew a contract before it expires?**
**A:** Yes, renewals can be initiated at any time. The new contract start date should be set appropriately.

---

## Best Practices

1. **Initiate renewals 60-90 days before expiry** to allow time for approval
2. **Include detailed notes** explaining the reason for renewal and any changes
3. **Review employee performance** before proposing salary increases
4. **Communicate with employees** about their contract status
5. **Keep terms consistent** unless there's a specific reason for changes

---

## System Configuration

### **Renewal Notice Periods**
- Default: 60 days before expiry
- Can be customized per contract
- Configurable in Contract Settings

### **Auto-Renewal**
- Some contracts can be set to auto-renew
- Still requires Admin approval
- Useful for permanent staff on fixed-term contracts

---

## Related Documentation

- Contract Management User Guide
- HR Functions Manual
- Employee Onboarding Process
- Performance Review Integration

---

**Last Updated:** February 24, 2026
**Version:** 1.0
**Workflow Type:** Option B - HR-Initiated with Senior Approval
