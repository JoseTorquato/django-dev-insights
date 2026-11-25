import os

from django.http import HttpResponse
from django.shortcuts import render

from .models import Book


def books(request):
    if os.environ.get("SHOP_N_PLUS_ONE"):
        queryset = Book.objects.order_by("id")
    else:
        queryset = Book.objects.select_related("author").order_by("id")
    titles = []
    for book in queryset:
        titles.append(f"{book.title} by {book.author.name}")  # N+1 line
    extra = bool(os.environ.get("SHOP_EXTRA_TEMPLATE"))
    return render(request, "shop/books.html", {"titles": titles, "extra": extra})


def ping(request):
    return HttpResponse("ok")


def kinds(request):
    from django.contrib.contenttypes.models import ContentType

    # served from ContentType's process-wide cache once warm
    return HttpResponse(ContentType.objects.get_for_model(Book).model)


def stats(request):
    from .cache import author_count

    return HttpResponse(str(author_count()))
