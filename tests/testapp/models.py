from django.db import models


class Author(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        app_label = "testapp"


class Book(models.Model):
    title = models.CharField(max_length=50)
    author = models.ForeignKey(Author, on_delete=models.CASCADE)

    class Meta:
        app_label = "testapp"
