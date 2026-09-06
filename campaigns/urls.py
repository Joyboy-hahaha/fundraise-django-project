from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('signup/', views.signup, name='signup'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('campaign/new/', views.create_campaign, name='create_campaign'),
    path('campaign/<slug:slug>/', views.campaign_detail, name='campaign_detail'),
    path('campaign/<slug:slug>/edit/', views.edit_campaign, name='edit_campaign'),
    path('campaign/<slug:slug>/delete/', views.delete_campaign, name='delete_campaign'),
    path('payment/esewa/success/', views.esewa_payment_success, name='esewa_payment_success'),
    path('payment/esewa/failure/', views.esewa_payment_failure, name='esewa_payment_failure'),
]
