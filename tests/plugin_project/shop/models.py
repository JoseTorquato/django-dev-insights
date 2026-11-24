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
    if Author._meta.db_table not in connection.introspection.table_names():
        with connection.schema_editor() as editor:
            editor.create_model(Author)
            editor.create_model(Book)
    Book.objects.all().delete()
    Author.objects.all().delete()
    for i in range(3):
        Book.objects.create(
            title=f"book {i}", author=Author.objects.create(name=f"a{i}")
        )
