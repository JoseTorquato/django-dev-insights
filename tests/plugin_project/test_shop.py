import pytest
from django.test import Client


@pytest.mark.dev_insights
def test_books():
    assert Client().get("/books/").status_code == 200


@pytest.mark.dev_insights
def test_ping_twice():
    client = Client()
    client.get("/shop-nope/")
    assert client.get("/ping/").status_code == 200


def test_not_guarded():
    # no marker: never measured, never in the baseline
    Client().get("/books/")
