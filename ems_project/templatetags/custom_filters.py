from django import template
from datetime import date, timedelta

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
