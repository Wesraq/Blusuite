# File Cleanup Instructions

## Problem
`settings_company.html` has duplicate old code from **line 2160** to the end of the file.

## Solution
**Manually delete everything after line 2159**

### Steps:

1. **Open the file**: `templates/ems/settings_company.html`

2. **Go to line 2159** - You should see:
   ```django
   {% endblock %}
   ```

3. **Select everything from line 2160 to the end of file** (Ctrl+Shift+End)

4. **Delete** (press Delete key)

5. **Save** the file (Ctrl+S)

### Expected Result:
- File should end at line 2159 with `{% endblock %}`
- Total lines: **~2159** (instead of 2900+)
- No lint errors
- Clean, working payslip designer

### Current Status:
- Line 2159: `{% endblock %}` ✅  (correct - keep this)
- Line 2160+: Old duplicate HTML/JS ❌ (delete all of this)

### What Line 2160 Currently Shows:
```html
<option value="three_column">Three Column: Prepared | Approved | Received</option>
```
**This and everything after it should be deleted.**

### Alternative (if manual is hard):
You can also:
1. Copy lines 1-2159 to a new file
2. Delete the old file
3. Rename the new file

---

**After cleanup, refresh your browser and test the payslip designer!** 🚀
