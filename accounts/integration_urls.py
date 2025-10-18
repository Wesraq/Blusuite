"""
URL patterns for integration management
"""
from django.urls import path
from accounts import integration_views

urlpatterns = [
    path('', integration_views.integration_management, name='integration_management'),
    path('connect/<int:integration_id>/', integration_views.integration_connect, name='integration_connect'),
    path('disconnect/<int:integration_id>/', integration_views.integration_disconnect, name='integration_disconnect'),
    path('test/<int:integration_id>/', integration_views.integration_test, name='integration_test'),
    path('oauth/callback/<int:integration_id>/', integration_views.integration_oauth_callback, name='integration_oauth_callback'),
    path('webhook/<int:company_id>/<int:integration_id>/<str:webhook_secret>/', integration_views.integration_webhook, name='integration_webhook'),
]
