from django import template

register = template.Library()

@register.filter
def hex_to_rgb(hex_color):
    """Convert hex color to RGB values"""
    if not hex_color or not hex_color.startswith('#'):
        return "59, 130, 246"  # Default blue
    
    hex_color = hex_color.lstrip('#')
    
    try:
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            return f"{r}, {g}, {b}"
        elif len(hex_color) == 3:
            r = int(hex_color[0] * 2, 16)
            g = int(hex_color[1] * 2, 16)
            b = int(hex_color[2] * 2, 16)
            return f"{r}, {g}, {b}"
    except ValueError:
        pass
    
    return "59, 130, 246"  # Default blue


@register.filter
def lighten_color(hex_color, amount=20):
    """Lighten a hex color by a percentage"""
    if not hex_color or not hex_color.startswith('#'):
        return "#3b82f6"
    
    hex_color = hex_color.lstrip('#')
    
    try:
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Lighten by moving towards white
            r = min(255, r + int((255 - r) * amount / 100))
            g = min(255, g + int((255 - g) * amount / 100))
            b = min(255, b + int((255 - b) * amount / 100))
            
            return f"#{r:02x}{g:02x}{b:02x}"
    except ValueError:
        pass
    
    return "#3b82f6"


@register.filter
def darken_color(hex_color, amount=20):
    """Darken a hex color by a percentage"""
    if not hex_color or not hex_color.startswith('#'):
        return "#3b82f6"
    
    hex_color = hex_color.lstrip('#')
    
    try:
        if len(hex_color) == 6:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            
            # Darken by moving towards black
            r = max(0, r - int(r * amount / 100))
            g = max(0, g - int(g * amount / 100))
            b = max(0, b - int(b * amount / 100))
            
            return f"#{r:02x}{g:02x}{b:02x}"
    except ValueError:
        pass
    
    return "#3b82f6"
