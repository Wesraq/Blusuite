from django import template
from datetime import date, timedelta
import re

register = template.Library()

@register.filter
def is_expired(expiry_date):
    """Check if a date is in the past"""
    if not expiry_date:
        return False
    return expiry_date < date.today()

@register.filter
def is_expiring_soon(expiry_date):
    """Check if a date is within 30 days"""
    if not expiry_date:
        return False
    today = date.today()
    return expiry_date >= today and expiry_date <= today + timedelta(days=30)

@register.filter
def strip_emoji(value):
    """Remove emoji characters from a string"""
    if not value:
        return value
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001f926-\U0001f937"
        "\U00010000-\U0010ffff"
        "\u2640-\u2642"
        "\u2600-\u2B55"
        "\u200d"
        "\u23cf"
        "\u23e9"
        "\u231a"
        "\ufe0f"
        "\u3030"
        "]+", flags=re.UNICODE
    )
    return emoji_pattern.sub('', str(value)).strip()
