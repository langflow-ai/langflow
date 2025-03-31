import json

import pytest
from langflow.services.database.utils import truncate_json


@pytest.fixture
def small_json():
    return [
        {"name": "Cole Ramos", "email": "egestas.fusce.aliquet@google.couk"},
        {"name": "Chancellor Torres", "email": "lorem.eu@hotmail.com"},
        {"name": "Deanna Lyons", "email": "neque.venenatis.lacus@outlook.couk"},
        {"name": "Ruby O'connor", "email": "lectus.justo.eu@hotmail.couk"},
        {"name": "Iona Dorsey", "email": "rutrum@yahoo.org"},
    ]


@pytest.fixture
def large_json():
    return [
        {
            "name": "Nash Briggs",
            "phone": "1-827-252-5669",
            "email": "magna.ut@icloud.edu",
            "address": "847-2983 Vel Rd.",
            "list": 5,
            "country": "South Korea",
            "region": "Gilgit Baltistan",
            "postalZip": "6088-8521",
            "text": "ipsum. Curabitur consequat, lectus sit amet luctus vulputate, nisi sem",
            "alphanumeric": "OJG47QKX4DO",
            "currency": "$46.88",
            "numberrange": 6,
        },
        {
            "name": "Keefe Cooley",
            "phone": "(164) 954-5395",
            "email": "congue.turpis.in@protonmail.ca",
            "address": "Ap #674-3382 Egestas. St.",
            "list": 3,
            "country": "Spain",
            "region": "Antioquia",
            "postalZip": "42452",
            "text": "nisl. Nulla eu neque pellentesque massa lobortis ultrices. Vivamus rhoncus.",
            "alphanumeric": "FIE81ZDK2RI",
            "currency": "$37.74",
            "numberrange": 3,
        },
        {
            "name": "Randall Booth",
            "phone": "(762) 778-9833",
            "email": "a@icloud.edu",
            "address": "Ap #116-8418 Nec Ave",
            "list": 9,
            "country": "Norway",
            "region": "Prince Edward Island",
            "postalZip": "39155",
            "text": "tempor arcu. Vestibulum ut eros non enim commodo hendrerit. Donec",
            "alphanumeric": "GMF33SGB4XD",
            "currency": "$87.24",
            "numberrange": 0,
        },
        {
            "name": "Aurora Mooney",
            "phone": "(626) 435-3885",
            "email": "morbi.sit.amet@icloud.org",
            "address": "837-8038 Duis Rd.",
            "list": 15,
            "country": "United States",
            "region": "West Sulawesi",
            "postalZip": "84466-29328",
            "text": "metus eu erat semper rutrum. Fusce dolor quam, elementum at,",
            "alphanumeric": "CVK31QJA8GZ",
            "currency": "$85.97",
            "numberrange": 1,
        },
        {
            "name": "Irma Snider",
            "phone": "1-682-186-4584",
            "email": "senectus.et@hotmail.org",
            "address": "718-8593 Mauris. Avenue",
            "list": 13,
            "country": "Italy",
            "region": "East Region",
            "postalZip": "47178",
            "text": "Cras convallis convallis dolor. Quisque tincidunt pede ac urna. Ut",
            "alphanumeric": "KXR03TWX8QA",
            "currency": "$65.54",
            "numberrange": 3,
        },
    ]


def test_truncate_json__small_case(small_json):
    max_size = 400

    result = truncate_json(small_json, max_size=max_size)

    assert len(str(small_json)) < max_size, "small_json must be smaller than max_size"
    assert result == small_json, "small_json should not be truncated"


def test_truncate_json__large_case(large_json):
    max_size = 1000

    result = truncate_json(large_json, max_size=max_size)

    assert len(str(large_json)) > max_size, "large_json must be larger than max_size"
    assert len(str(result)) < len(str(large_json)), "result must be smaller than large_json"
    assert json.dumps(result), "result must be a valid JSON object"
