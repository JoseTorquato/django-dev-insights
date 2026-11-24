"""Create the test tables once per connection (SQLite in memory)."""

from django.db import connection

from .models import Author, Book


def create_tables():
    existing = set(connection.introspection.table_names())
    with connection.schema_editor() as editor:
        for model in (Author, Book):
            if model._meta.db_table not in existing:
                editor.create_model(model)


def seed(authors=3, books_per_author=1):
    Book.objects.all().delete()
    Author.objects.all().delete()
    for i in range(authors):
        author = Author.objects.create(name=f"author {i}")
        for j in range(books_per_author):
            Book.objects.create(title=f"book {i}.{j}", author=author)
