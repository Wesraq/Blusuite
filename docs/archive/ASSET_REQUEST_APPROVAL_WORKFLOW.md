# Asset Request Approval Workflow Documentation

## Overview
The asset request system now supports **department-based approval routing** with multi-level hierarchical approvals. This ensures proper oversight and budget control while maintaining flexibility for different department needs.

---

## Approval Hierarchy for Ordinary Employees

### General Workflow
```
Employee → Supervisor → Department Manager → HR → Admin/Procurement
```

### Department-Specific Routing

#### 1. **IT/Technology Departments**
- **Workflow**: Employee → Supervisor → Manager → Admin
- **Skips**: HR review (technical assets don't require HR policy review)
- **Applies to**: 
  - Departments with "IT" or "TECH" in name
  - Asset types: LAPTOP, DESKTOP, SOFTWARE

#### 2. **HR Department**
- **Workflow**: Employee → Manager → Admin
- **Skips**: Supervisor review (HR managers directly oversee), HR review (self-review not needed)
- **Applies to**: Departments with "HR" or "HUMAN" in name

#### 3. **Finance/Accounting Departments**
- **Workflow**: Employee → Manager → Admin
- **Skips**: Supervisor review, HR review
- **Applies to**: Departments with "FINANCE" or "ACCOUNT" in name

#### 4. **All Other Departments**
- **Workflow**: Employee → Supervisor → Manager → HR → Admin
- **Full approval chain** for comprehensive oversight

---

## Approval Levels Explained

### Level 1: Supervisor Review
- **Who**: Direct supervisor/line manager
- **Purpose**: Verify immediate need and employee justification
- **Can approve**: Users with SUPERVISOR role in same department
- **Actions**: Approve or Reject

### Level 2: Department Manager
- **Who**: Department head/manager
- **Purpose**: Budget approval and departmental priority assessment
- **Can approve**: Users with DEPARTMENT_MANAGER or SUPERVISOR role in same department
- **Actions**: Approve or Reject

### Level 3: HR Review
- **Who**: HR personnel
- **Purpose**: Company policy compliance, employee eligibility check
- **Can approve**: Users with employee_type = 'HR'
- **Actions**: Approve or Reject
- **Note**: Skipped for IT/Tech, HR, and Finance departments

### Level 4: Admin/Procurement
- **Who**: System administrators or procurement team
- **Purpose**: Final approval, budget allocation, procurement initiation
- **Can approve**: Users with SUPERADMIN, ADMINISTRATOR, or EMPLOYER_ADMIN role
- **Actions**: Approve, Reject, or Fulfill

---

## Request Status Flow

```
PENDING → (approvals) → APPROVED → FULFILLED
   ↓
REJECTED (at any level)
```

### Status Definitions

- **PENDING**: Request submitted, awaiting approvals
- **APPROVED**: All approvals obtained, ready for procurement
- **REJECTED**: Denied at any approval level
- **FULFILLED**: Asset procured and assigned to employee

---

## Model Fields

### Core Fields
- `requested_by`: Employee who created the request
- `department`: Employee's department (determines workflow)
- `asset_type`, `asset_name`, `description`: Asset details
- `quantity`, `estimated_cost`: Procurement info
- `priority`: LOW, MEDIUM, HIGH, URGENT
- `status`: PENDING, APPROVED, REJECTED, FULFILLED

### Approval Tracking Fields
- `current_approval_level`: Current stage (SUPERVISOR, MANAGER, HR, ADMIN)
- `supervisor_approved`, `supervisor_approved_by`, `supervisor_approval_date`
- `manager_approved`, `manager_approved_by`, `manager_approval_date`
- `hr_approved`, `hr_approved_by`, `hr_approval_date`
- `approved_by`, `approval_date`: Final admin approval
- `rejection_reason`: Why request was denied
- `admin_notes`: Internal notes for procurement

---

## Key Model Methods

### `get_approval_workflow()`
Returns the list of approval levels required for this specific request based on department and asset type.

### `get_next_approval_level()`
Determines the next approval level in the workflow after current level is approved.

### `is_approval_complete()`
Checks if all required approvals have been obtained.

### `get_pending_approver_role()`
Returns human-readable role of who needs to approve next (e.g., "Supervisor", "Department Manager").

### `can_user_approve(user)`
Validates if a specific user has permission to approve at the current level.

---

## Usage Example

### For Regular Employee
1. Navigate to "My Assets" → Click "Request Asset"
2. Fill in asset details and justification
3. Submit request
4. Request goes to supervisor (or manager if no supervisor level)
5. Track approval status in "My Requests"

### For Supervisor
1. Receive notification of pending request
2. Review request details and employee justification
3. Approve or reject with optional notes
4. If approved, automatically routes to next level (Manager)

### For Department Manager
1. Review requests that passed supervisor approval
2. Assess budget impact and departmental priority
3. Approve or reject
4. If approved, routes to HR (or Admin for IT/Finance/HR depts)

### For HR
1. Review requests for policy compliance
2. Verify employee eligibility
3. Approve or reject
4. If approved, routes to Admin for final approval

### For Admin/Procurement
1. Review all approved requests
2. Final budget approval
3. Approve for procurement or reject
4. Once fulfilled, mark as FULFILLED and assign asset

---

## Integration with E-Forms

**Decision**: Asset requests remain a **dedicated module** (not using E-Forms) because:

1. **Specialized logic**: Inventory checking, cost tracking, fulfillment workflow
2. **Direct asset assignment**: Approved requests create actual assets
3. **Department budget analytics**: Track spending by department
4. **Recurring requests**: Handle bulk and repeat orders
5. **Procurement integration**: Link to vendor management

E-Forms is better suited for:
- General employee requests (leave, reimbursement, etc.)
- Custom approval workflows per form type
- Document collection and signatures

---

## Next Steps (Implementation)

1. ✅ Enhanced AssetRequest model with approval fields
2. ⏳ Create database migration
3. ⏳ Update asset_request_create view to set initial approval level
4. ⏳ Create asset_request_approve view for approval actions
5. ⏳ Update asset_request_list to show approval status
6. ⏳ Create asset_request_detail with approval timeline
7. ⏳ Add email notifications for approval requests
8. ⏳ Update templates to show approval chain progress

---

## Benefits

✅ **Clear accountability**: Each approval level has specific responsibility
✅ **Flexible routing**: Different workflows for different departments
✅ **Audit trail**: Complete history of who approved what and when
✅ **Scalable**: Easy to add new approval levels or modify workflows
✅ **Role-based**: Automatic permission checking based on user role and department
