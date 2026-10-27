from django.contrib import admin
from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView


app_name = 'users'

urlpatterns = [
    path('', views.LoginUserView.as_view(), name='login'  ),
    path('dashboard/', views.DashboardView.as_view(), name='dashboard' ),
    path("logout/", LogoutView.as_view(), name="logout"),
]
