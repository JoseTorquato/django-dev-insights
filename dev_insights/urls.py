from django.urls import path

from .views import panel_view

app_name = "dev_insights"

urlpatterns = [
    path("", panel_view, name="panel"),
]
