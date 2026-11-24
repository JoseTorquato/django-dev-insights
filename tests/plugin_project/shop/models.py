from django.db import connection, models


class Author(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        app_label = "shop"


class Book(models.Model):
    title = models.CharField(max_length=50)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

    class Meta:
        app_label = "shop"


def create_and_seed():
    from django.contrib.contenttypes.models import ContentType

    tables = connection.introspection.table_names()
    if Author._meta.db_table not in tables:
        with connection.schema_editor() as editor:
            editor.create_model(ContentType)
            editor.create_model(Author)
            editor.create_model(Book)
    # the row exists, but ContentType's in-memory cache stays cold
    ContentType.objects.get_or_create(app_label="shop", model="book")
    Book.objects.all().delete()
    Author.objects.all().delete()
    for i in range(3):
        Book.objects.create(
            title=f"book {i}", author=Author.objects.create(name=f"a{i}")
        )
