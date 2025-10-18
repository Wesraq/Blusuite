# Payslip Designer V2 Rebuild - Ready to Implement

## What Will Change

### Old Layout (Lines 1417-1685)
- 3 columns: Fields sidebar | Canvas | Properties
- Drag and drop fields
- Search and category filter

### New Layout
- 2 columns: Tabbed Editor (480px) | Live Preview (flexible)
- 6 tabs with forms
- No drag-and-drop

## Implementation Steps

1. **Replace lines 1417-1685** with new structure
2. **Add new CSS** for tabs and toggles
3. **Update JavaScript** for tab switching and calculations

## Ready to Execute

The rebuild will:
- Keep same Django form structure
- Maintain CSRF and hidden inputs
- Use same color variables
- Save to same backend endpoint

**Next:** Replace the section in settings_company.html

Lines to replace: 1417 to 1685 (268 lines)
New code: ~400 lines (more features)
