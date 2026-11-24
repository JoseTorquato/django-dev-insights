from django.urls import path

from . import views

app_name = "shop"
urlpatterns = [
    path("books/", views.books, name="books"),
    path("ping/", views.ping, name="ping"),
]
