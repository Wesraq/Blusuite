# Remaining EMS Issues - Implementation Guide

## Issue 5: Administrator Dashboard Enhancement

### Current Implementation
The administrator dashboard at `ems_project/templates/ems/admin_dashboard_new.html` shows basic metrics but lacks visual appeal and comprehensive insights.

### Required Enhancements

#### 1. Add Attendance Trend Chart (Last 30 Days)
**Location**: After the "Attendance Overview" section

```html
<!-- Attendance Trend Chart -->
<div style="background: white; border: 1px solid #e2e8f0; border-radius: 12px; padding: 20px; grid-column: span 2;">
    <h3 style="margin: 0 0 16px 0; color: #0f172a; font-size: 18px; font-weight: 600;">30-Day Attendance Trend</h3>
    <canvas id="attendanceChart" height="80"></canvas>
</div>
```

**JavaScript** (add to bottom of template):
```javascript
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<script>
const ctx = document.getElementById('attendanceChart');
new Chart(ctx, {
    type: 'line',
    data: {
        labels: {{ attendance_dates|safe }},
        datasets: [{
            label: 'Present',
            data: {{ attendance_present|safe }},
            borderColor: '#10b981',
            backgroundColor: 'rgba(16, 185, 129, 0.1)',
            tension: 0.4
        }, {
            label: 'Absent',
            data: {{ attendance_absent|safe }},
            borderColor: '#ef4444',
            backgroundColor: 'rgba(239, 68, 68, 0.1)',
            tension: 0.4
        }]
    },
    options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: {
            legend: { position: 'top' }
        }
    }
});
</script>
```

**Backend** (add to `employer_dashboard` view):
```python
# 30-day attendance trend
from datetime import timedelta
attendance_dates = []
attendance_present = []
attendance_absent = []

for i in range(29, -1, -1):
    day = today - timedelta(days=i)
    day_attendance = Attendance.objects.filter(
        employee__in=employees,
        date=day
    )
    present = day_attendance.filter(status='PRESENT').count()
    absent = total_employees - present if total_employees > 0 else 0
    
    attendance_dates.append(day.strftime('%b %d'))
    attendance_present.append(present)
    attendance_absent.append(absent)

context['attendance_dates'] = json.dumps(attendance_dates)
context['attendance_present'] = json.dumps(attendance_present)
context['attendance_absent'] = json.dumps(attendance_absent)
```

#### 2. Add Quick Insights Section
```html
<!-- Quick Insights -->
<div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 12px; padding: 24px; color: white; grid-column: span 2;">
    <h3 style="margin: 0 0 20px 0; font-size: 18px; font-weight: 600; display: flex; align-items: center; gap: 8px;">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"></path>
        </svg>
        Quick Insights
    </h3>
    <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px;">
        <div style="background: rgba(255,255,255,0.15); padding: 16px; border-radius: 8px; backdrop-filter: blur(10px);">
            <div style="font-size: 13px; opacity: 0.9; margin-bottom: 4px;">Attendance Rate</div>
            <div style="font-size: 28px; font-weight: 700;">{{ attendance_rate|floatformat:1 }}%</div>
        </div>
        <div style="background: rgba(255,255,255,0.15); padding: 16px; border-radius: 8px; backdrop-filter: blur(10px);">
            <div style="font-size: 13px; opacity: 0.9; margin-bottom: 4px;">On Leave Today</div>
            <div style="font-size: 28px; font-weight: 700;">{{ on_leave_today }}</div>
        </div>
        <div style="background: rgba(255,255,255,0.15); padding: 16px; border-radius: 8px; backdrop-filter: blur(10px);">
            <div style="font-size: 13px; opacity: 0.9; margin-bottom: 4px;">New Hires (30d)</div>
            <div style="font-size: 28px; font-weight: 700;">{{ new_hires_month }}</div>
        </div>
        <div style="background: rgba(255,255,255,0.15); padding: 16px; border-radius: 8px; backdrop-filter: blur(10px);">
            <div style="font-size: 13px; opacity: 0.9; margin-bottom: 4px;">Attrition Rate</div>
            <div style="font-size: 28px; font-weight: 700;">{{ attrition_rate }}%</div>
        </div>
    </div>
</div>
```

---

## Issue 6: Attendance Recording from Employee Profile

### Investigation Steps

1. **Find the clock in/out implementation**:
```bash
grep -r "clock.*in\|clock.*out" ems_project/templates/ems/employee*.html
```

2. **Check the AJAX endpoint**:
Look for attendance recording endpoint in `frontend_views.py`:
```python
@login_required
@require_POST
def record_attendance(request):
    # This should handle clock in/out
```

3. **Common Issues to Check**:

#### Missing CSRF Token
```html
<!-- Ensure form has CSRF token -->
<form id="attendance-form">
    {% csrf_token %}
    <button type="button" onclick="clockIn()">Clock In</button>
</form>
```

#### JavaScript AJAX Call
```javascript
function clockIn() {
    const csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;
    
    fetch('/attendance/clock-in/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': csrftoken
        },
        body: JSON.stringify({
            employee_id: '{{ user.id }}',
            timestamp: new Date().toISOString()
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('Clocked in successfully!');
            location.reload();
        } else {
            alert('Error: ' + data.error);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Failed to clock in. Please try again.');
    });
}
```

#### Backend View Fix
```python
@login_required
@require_POST
def clock_in(request):
    from attendance.models import Attendance
    from django.utils import timezone
    
    try:
        employee = request.user
        today = timezone.now().date()
        
        # Check if already clocked in today
        existing = Attendance.objects.filter(
            employee=employee,
            date=today
        ).first()
        
        if existing and existing.clock_in_time:
            return JsonResponse({
                'success': False,
                'error': 'Already clocked in today'
            })
        
        # Create or update attendance record
        attendance, created = Attendance.objects.get_or_create(
            employee=employee,
            date=today,
            defaults={
                'clock_in_time': timezone.now().time(),
                'status': 'PRESENT'
            }
        )
        
        if not created:
            attendance.clock_in_time = timezone.now().time()
            attendance.status = 'PRESENT'
            attendance.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Clocked in successfully',
            'time': attendance.clock_in_time.strftime('%H:%M:%S')
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)
```

---

## Issue 7: Monthly Attendance Overview UI Enhancement

### CSS Fixes

Add to `ems_project/templates/ems/attendance_dashboard.html`:

```css
<style>
/* Enhanced Attendance Matrix Styling */
.attendance-matrix {
    width: 100%;
    border-collapse: separate;
    border-spacing: 0;
    font-size: 13px;
}

.attendance-matrix thead th {
    background: #f8fafc;
    color: #475569;
    font-weight: 600;
    padding: 12px 8px;
    text-align: center;
    border-bottom: 2px solid #e2e8f0;
    position: sticky;
    top: 0;
    z-index: 10;
}

.attendance-matrix tbody td {
    min-width: 45px;
    max-width: 45px;
    padding: 10px 6px;
    text-align: center;
    border: 1px solid #f1f5f9;
    vertical-align: middle;
}

.attendance-matrix tbody td:first-child {
    min-width: 180px;
    max-width: 180px;
    text-align: left;
    padding-left: 12px;
    font-weight: 500;
    position: sticky;
    left: 0;
    background: white;
    z-index: 5;
}

/* Status Badges */
.status-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 32px;
    height: 32px;
    padding: 6px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
    line-height: 1;
    cursor: pointer;
    transition: all 0.2s;
}

.status-badge:hover {
    transform: scale(1.1);
    box-shadow: 0 2px 8px rgba(0,0,0,0.15);
}

/* Status Colors */
.status-badge.present {
    background: #d1fae5;
    color: #065f46;
}

.status-badge.absent {
    background: #fee2e2;
    color: #991b1b;
}

.status-badge.late {
    background: #fef3c7;
    color: #92400e;
}

.status-badge.half-day {
    background: #e0e7ff;
    color: #3730a3;
}

.status-badge.leave {
    background: #dbeafe;
    color: #1e40af;
}

.status-badge.holiday {
    background: #f3e8ff;
    color: #6b21a8;
}

.status-badge.weekend {
    background: #f1f5f9;
    color: #64748b;
}

/* Tooltip on hover */
.status-badge[title] {
    position: relative;
}

.status-badge[title]:hover::after {
    content: attr(title);
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: #1e293b;
    color: white;
    padding: 6px 10px;
    border-radius: 4px;
    font-size: 11px;
    white-space: nowrap;
    z-index: 1000;
    margin-bottom: 4px;
}

/* Legend */
.attendance-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 16px;
    padding: 16px;
    background: #f8fafc;
    border-radius: 8px;
    margin-bottom: 20px;
}

.legend-item {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
}

.legend-color {
    width: 24px;
    height: 24px;
    border-radius: 4px;
}

/* Responsive */
@media (max-width: 768px) {
    .attendance-matrix {
        font-size: 11px;
    }
    
    .attendance-matrix tbody td {
        min-width: 36px;
        max-width: 36px;
        padding: 8px 4px;
    }
    
    .status-badge {
        min-width: 28px;
        height: 28px;
        font-size: 10px;
    }
}
</style>
```

### HTML Structure Update

```html
<!-- Add Legend -->
<div class="attendance-legend">
    <div class="legend-item">
        <div class="legend-color" style="background: #d1fae5;"></div>
        <span>Present (P)</span>
    </div>
    <div class="legend-item">
        <div class="legend-color" style="background: #fee2e2;"></div>
        <span>Absent (A)</span>
    </div>
    <div class="legend-item">
        <div class="legend-color" style="background: #fef3c7;"></div>
        <span>Late (L)</span>
    </div>
    <div class="legend-item">
        <div class="legend-color" style="background: #e0e7ff;"></div>
        <span>Half Day (H)</span>
    </div>
    <div class="legend-item">
        <div class="legend-color" style="background: #dbeafe;"></div>
        <span>Leave (LV)</span>
    </div>
    <div class="legend-item">
        <div class="legend-color" style="background: #f1f5f9;"></div>
        <span>Weekend (W)</span>
    </div>
</div>

<!-- Update status cells -->
<td>
    <span class="status-badge {{ status|lower }}" 
          title="{{ employee.name }} - {{ date }} - {{ status_full }}">
        {{ status_short }}
    </span>
</td>
```

---

## Issue 8: Performance Review Enhancement

### Form Enhancements

Create enhanced form at `ems_project/templates/ems/performance_review_form_enhanced.html`:

```html
{% extends 'ems/base_employer.html' %}

{% block content %}
<div class="page-header">
    <h2>Performance Review - {{ employee.get_full_name }}</h2>
    <p>Comprehensive performance evaluation</p>
</div>

<form method="post" enctype="multipart/form-data" class="performance-form">
    {% csrf_token %}
    
    <!-- Section 1: Basic Information -->
    <div class="review-section">
        <h3>Review Information</h3>
        <div class="form-grid">
            <div class="form-group">
                <label>Review Period</label>
                <select name="review_period" required>
                    <option value="Q1">Q1 (Jan-Mar)</option>
                    <option value="Q2">Q2 (Apr-Jun)</option>
                    <option value="Q3">Q3 (Jul-Sep)</option>
                    <option value="Q4">Q4 (Oct-Dec)</option>
                    <option value="ANNUAL">Annual</option>
                    <option value="PROBATION">Probation</option>
                </select>
            </div>
            <div class="form-group">
                <label>Review Date</label>
                <input type="date" name="review_date" required>
            </div>
        </div>
    </div>

    <!-- Section 2: Performance Ratings -->
    <div class="review-section">
        <h3>Performance Ratings</h3>
        
        {% for competency in competencies %}
        <div class="rating-item">
            <label>{{ competency.name }}</label>
            <div class="star-rating" data-name="{{ competency.id }}">
                {% for i in "12345" %}
                <span class="star" data-value="{{ i }}">★</span>
                {% endfor %}
            </div>
            <input type="hidden" name="rating_{{ competency.id }}" value="0">
            <textarea name="comment_{{ competency.id }}" 
                      placeholder="Comments on {{ competency.name }}..." 
                      rows="2"></textarea>
        </div>
        {% endfor %}
    </div>

    <!-- Section 3: Goals & Achievements -->
    <div class="review-section">
        <h3>Goals & Achievements</h3>
        <div class="form-group">
            <label>Goals Achieved</label>
            <textarea name="goals_achieved" rows="4" 
                      placeholder="List goals achieved during this period..."></textarea>
        </div>
        <div class="form-group">
            <label>Key Accomplishments</label>
            <textarea name="accomplishments" rows="4" 
                      placeholder="Notable achievements and contributions..."></textarea>
        </div>
    </div>

    <!-- Section 4: Areas for Improvement -->
    <div class="review-section">
        <h3>Development Areas</h3>
        <div class="form-group">
            <label>Areas for Improvement</label>
            <textarea name="improvement_areas" rows="4" 
                      placeholder="Skills or behaviors to develop..."></textarea>
        </div>
        <div class="form-group">
            <label>Development Plan</label>
            <textarea name="development_plan" rows="4" 
                      placeholder="Training, mentoring, or development activities..."></textarea>
        </div>
    </div>

    <!-- Section 5: Goals for Next Period -->
    <div class="review-section">
        <h3>Goals for Next Period</h3>
        <div id="goals-container">
            <div class="goal-item">
                <input type="text" name="goal_1" placeholder="SMART Goal 1" class="form-control">
                <input type="date" name="goal_1_deadline" class="form-control">
            </div>
        </div>
        <button type="button" onclick="addGoal()" class="btn-secondary">+ Add Goal</button>
    </div>

    <!-- Section 6: Overall Assessment -->
    <div class="review-section">
        <h3>Overall Assessment</h3>
        <div class="form-group">
            <label>Overall Rating</label>
            <select name="overall_rating" required>
                <option value="5">Outstanding (5)</option>
                <option value="4">Exceeds Expectations (4)</option>
                <option value="3" selected>Meets Expectations (3)</option>
                <option value="2">Needs Improvement (2)</option>
                <option value="1">Unsatisfactory (1)</option>
            </select>
        </div>
        <div class="form-group">
            <label>Overall Comments</label>
            <textarea name="overall_comments" rows="4" required></textarea>
        </div>
        <div class="form-group">
            <label>Recommendation</label>
            <select name="recommendation">
                <option value="PROMOTION">Recommend for Promotion</option>
                <option value="SALARY_INCREASE">Recommend Salary Increase</option>
                <option value="CONTINUE">Continue in Current Role</option>
                <option value="PIP">Performance Improvement Plan</option>
                <option value="TERMINATION">Consider Termination</option>
            </select>
        </div>
    </div>

    <!-- Section 7: Attachments -->
    <div class="review-section">
        <h3>Supporting Documents</h3>
        <div class="form-group">
            <label>Attach Files (optional)</label>
            <input type="file" name="attachments" multiple accept=".pdf,.doc,.docx">
            <small>PDF, DOC, DOCX files only</small>
        </div>
    </div>

    <div class="form-actions">
        <button type="submit" name="status" value="DRAFT" class="btn-secondary">Save as Draft</button>
        <button type="submit" name="status" value="COMPLETED" class="btn">Submit Review</button>
    </div>
</form>

<script>
// Star rating functionality
document.querySelectorAll('.star-rating').forEach(rating => {
    const stars = rating.querySelectorAll('.star');
    const input = rating.nextElementSibling;
    
    stars.forEach((star, index) => {
        star.addEventListener('click', () => {
            const value = index + 1;
            input.value = value;
            stars.forEach((s, i) => {
                s.classList.toggle('active', i < value);
            });
        });
    });
});

// Add goal functionality
let goalCount = 1;
function addGoal() {
    goalCount++;
    const container = document.getElementById('goals-container');
    const div = document.createElement('div');
    div.className = 'goal-item';
    div.innerHTML = `
        <input type="text" name="goal_${goalCount}" placeholder="SMART Goal ${goalCount}" class="form-control">
        <input type="date" name="goal_${goalCount}_deadline" class="form-control">
        <button type="button" onclick="this.parentElement.remove()" class="btn-danger">×</button>
    `;
    container.appendChild(div);
}
</script>

<style>
.review-section {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    padding: 24px;
    margin-bottom: 20px;
}

.review-section h3 {
    font-size: 18px;
    font-weight: 600;
    color: #1e293b;
    margin-bottom: 20px;
    padding-bottom: 12px;
    border-bottom: 2px solid #fecdd3;
}

.form-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 16px;
}

.rating-item {
    padding: 16px;
    background: #f8fafc;
    border-radius: 6px;
    margin-bottom: 16px;
}

.star-rating {
    display: flex;
    gap: 4px;
    margin: 8px 0;
}

.star {
    font-size: 28px;
    color: #cbd5e1;
    cursor: pointer;
    transition: all 0.2s;
}

.star:hover,
.star.active {
    color: #fbbf24;
    transform: scale(1.1);
}

.goal-item {
    display: grid;
    grid-template-columns: 1fr auto auto;
    gap: 12px;
    margin-bottom: 12px;
}

.form-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
    margin-top: 24px;
}
</style>
{% endblock %}
```

---

## Issue 9: Company Logo Upload Fix

### Quick Fix Implementation

**File**: `ems_project/frontend_views.py` (around line 6688)

The code already handles logo upload correctly:
```python
if 'company_logo' in request.FILES:
    company.logo = request.FILES['company_logo']
```

**The issue is likely in the template**. Check `settings_company.html` for the form:

```html
<!-- ENSURE THIS IS PRESENT -->
<form method="post" enctype="multipart/form-data" action="{% url 'settings_dashboard' %}">
    {% csrf_token %}
    <input type="hidden" name="action" value="company_profile">
    
    <div class="form-group">
        <label>Company Logo</label>
        {% if company.logo %}
        <div style="margin-bottom: 12px;">
            <img src="{{ company.logo.url }}" alt="Current Logo" style="max-width: 200px; border-radius: 8px;">
        </div>
        {% endif %}
        <input type="file" name="company_logo" accept="image/*" class="form-control">
        <small>Recommended: PNG or JPG, max 2MB</small>
    </div>
    
    <button type="submit" class="btn">Save Company Profile</button>
</form>
```

**Critical**: The form MUST have `enctype="multipart/form-data"` attribute!

---

## Testing Checklist

After implementing fixes:

- [ ] Administrator can see Attendance module in sidebar
- [ ] No dual highlighting when accessing Employee Requests
- [ ] Training form shows all new fields (capacity, location, prerequisites, etc.)
- [ ] Company logo can be uploaded and saved
- [ ] Employee clock in/out creates attendance records
- [ ] Monthly attendance overview has proper spacing and styling
- [ ] Performance review form has enhanced fields
- [ ] Dashboard shows attendance trend chart

---

**Document Created**: February 14, 2026  
**Status**: Implementation guide for remaining issues 5-9
