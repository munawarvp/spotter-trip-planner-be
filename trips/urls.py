from django.urls import path
from . import views

urlpatterns = [
    path('plan/', views.plan_trip, name='plan_trip'),
]