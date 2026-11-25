from django.urls import path

from . import views

app_name = "shop"
urlpatterns = [
    path("books/", views.books, name="books"),
    path("ping/", views.ping, name="ping"),
    path("kinds/", views.kinds, name="kinds"),
    path("stats/", views.stats, name="stats"),
]
