"""
Custom error handlers for EMS
"""
from django.shortcuts import render


def handler404(request, exception=None):
    """
    Custom 404 error handler
    """
    return render(request, '404.html', status=404)


def handler500(request):
    """
    Custom 500 error handler
    """
    return render(request, '500.html', status=500)


def handler403(request, exception=None):
    """
    Custom 403 error handler
    """
    return render(request, '403.html', status=403)
