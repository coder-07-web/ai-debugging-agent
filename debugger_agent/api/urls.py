from django.urls import path
from .views import debug_code

urlpatterns = [
    path('debug/', debug_code),
]