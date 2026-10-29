from django.urls import path

from . import views

urlpatterns = [
    path('health', views.health),
    path('plan', views.plan),
    path('heatmap', views.heatmap),
    path('places', views.places),
    path('places/reverse', views.reverse_place),
]
