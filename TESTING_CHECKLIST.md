# Testing Checklist for Asset Management & Training Modules

## Asset Management Module

### Admin Role Testing
- [ ] Access asset list at `/assets/`
- [ ] View asset details
- [ ] Create new asset request
- [ ] View all asset requests from all departments
- [ ] Approve/Reject asset requests at `/assets/requests/<id>/approve/`
- [ ] View department dashboard

### Department Manager Role Testing
- [ ] Access asset list (should see department assets only)
- [ ] View asset details for department assets
- [ ] Create asset request for department
- [ ] View department asset requests
- [ ] Access department asset dashboard at `/assets/department/dashboard/`
- [ ] Cannot approve/reject requests (admin only)

### Employee Role Testing
- [ ] Access asset list (limited view)
- [ ] View asset details
- [ ] Cannot create asset requests (manager only)
- [ ] Cannot access department dashboard

### Feature Testing
- [ ] Asset statistics display correctly
- [ ] Asset filters work (type, department, status)
- [ ] Asset search functionality
- [ ] Asset assignment tracking
- [ ] Maintenance history display
- [ ] Request status updates (Pending → Approved/Rejected)

---

## Training & Development Module

### Admin Role Testing
- [ ] Access training list at `/training/`
- [ ] View all company training programs
- [ ] View training details
- [ ] Enroll in training programs
- [ ] View all training requests from all departments
- [ ] Approve/Reject training requests at `/training/requests/<id>/approve/`
- [ ] View my training enrollments at `/training/my-training/`

### Department Manager Role Testing
- [ ] Access training list (department + company-wide programs)
- [ ] View training details
- [ ] Create training request at `/training/requests/create/`
- [ ] View department training requests
- [ ] Access department training dashboard at `/training/department/dashboard/`
- [ ] Enroll department employees in training
- [ ] View training statistics

### Employee Role Testing
- [ ] Access training list (company-wide programs only)
- [ ] View training details
- [ ] Enroll in available training programs
- [ ] View my training at `/training/my-training/`
- [ ] Track training progress
- [ ] View certificates
- [ ] Cannot create training requests

### Feature Testing
- [ ] Training program filters (type, department, status)
- [ ] Training search functionality
- [ ] Enrollment tracking (Enrolled → In Progress → Completed)
- [ ] Training statistics and progress bars
- [ ] Certificate display for completed training
- [ ] Training request workflow (Pending → Approved/Rejected)
- [ ] Priority indicators (Urgent, High, Medium, Low)
- [ ] Business justification and urgency reasons display

---

## Integration Testing

### Navigation
- [ ] Asset links accessible from main navigation
- [ ] Training links accessible from main navigation
- [ ] Breadcrumbs work correctly
- [ ] Back buttons navigate properly

### Permissions
- [ ] Role-based access control enforced
- [ ] Department-based filtering working
- [ ] Unauthorized access returns error/redirect
- [ ] Admin panel registration working

### Database
- [ ] All models registered in admin
- [ ] Foreign key relationships working
- [ ] Cascading deletes handled correctly
- [ ] Date/time fields populate correctly

### UI/UX
- [ ] Templates render without errors
- [ ] Responsive design working
- [ ] Icons display correctly
- [ ] Status badges show correct colors
- [ ] Forms validate properly
- [ ] Success/error messages display

---

## Test URLs

### Asset Management (New Department-Based System)
- Asset List: `http://127.0.0.1:8000/asset-management/`
- Asset Detail: `http://127.0.0.1:8000/asset-management/<id>/`
- Asset Request List: `http://127.0.0.1:8000/asset-management/requests/`
- Create Asset Request: `http://127.0.0.1:8000/asset-management/requests/create/`
- Approve Asset Request: `http://127.0.0.1:8000/asset-management/requests/<id>/approve/`
- Department Dashboard: `http://127.0.0.1:8000/asset-management/department/dashboard/`

### Asset Management (Legacy System)
- Legacy Asset List: `http://127.0.0.1:8000/assets/` (from navigation)

### Training & Development
- Training List: `http://127.0.0.1:8000/training/`
- Training Detail: `http://127.0.0.1:8000/training/<id>/`
- Enroll in Training: `http://127.0.0.1:8000/training/<id>/enroll/`
- My Training: `http://127.0.0.1:8000/training/my-training/`
- Training Request List: `http://127.0.0.1:8000/training/requests/`
- Create Training Request: `http://127.0.0.1:8000/training/requests/create/`
- Approve Training Request: `http://127.0.0.1:8000/training/requests/<id>/approve/`
- Department Dashboard: `http://127.0.0.1:8000/training/department/dashboard/`

---

## Known Issues / Notes
- Lint warnings in templates are false positives from CSS parser on inline Django template variables
- No migrations needed - models already exist in database
- Both modules use department-based access control
- Admin panel fully configured for both modules

---

## Test Data Requirements

### For Asset Testing
- At least 2 departments
- Admin user
- Department manager user
- Regular employee user
- Sample assets in database
- Sample asset requests

### For Training Testing
- At least 2 departments
- Admin user
- Department manager user
- Regular employee user
- Sample training programs
- Sample training enrollments
- Sample training requests

---

## Success Criteria
✅ All role-based permissions working correctly
✅ Department filtering working as expected
✅ Request/approval workflows functional
✅ Statistics and dashboards displaying accurate data
✅ No server errors or template rendering issues
✅ Forms submit and validate correctly
✅ Admin panel accessible and functional
