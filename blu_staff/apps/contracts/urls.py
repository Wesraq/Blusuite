from django.urls import path
from . import views

app_name = 'contracts'

urlpatterns = [
    path('', views.contracts_list, name='contracts_list'),
    path('<int:contract_id>/', views.contract_detail, name='contract_detail'),
    path('create/', views.contract_create, name='contract_create'),
    path('<int:contract_id>/edit/', views.contract_edit, name='contract_edit'),
    path('<int:contract_id>/renew/', views.contract_renew, name='contract_renew'),
    path('expiring/', views.expiring_contracts, name='expiring_contracts'),
    path('renewals/', views.renewal_requests, name='renewal_requests'),
    path('renewals/<int:renewal_id>/approve/', views.approve_renewal, name='approve_renewal'),
    path('renewals/<int:renewal_id>/reject/', views.reject_renewal, name='reject_renewal'),
]
