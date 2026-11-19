from ministore.pagination import list_orders
import pytest

ROWS = [
    {"id": "a", "created_at": 10},
    {"id": "d", "created_at": 10},
    {"id": "c", "created_at": 9},
    {"id": "b", "created_at": 10},
]


def test_order_uses_timestamp_then_id_descending():
    page = list_orders(ROWS, 2)
    assert [row["id"] for row in page["items"]] == ["d", "b"]


def test_cursor_is_exclusive_and_preserves_same_timestamp_rows():
    first = list_orders(ROWS, 2)
    second = list_orders(ROWS, 2, first["next_cursor"])
    assert [row["id"] for row in second["items"]] == ["a", "c"]
    assert not ({row["id"] for row in first["items"]} & {row["id"] for row in second["items"]})


def test_next_cursor_comes_from_last_item_in_current_page():
    first = list_orders(ROWS, 2)
    assert first["next_cursor"] == "10|b"


def test_exactly_one_page_has_no_next_cursor():
    page = list_orders(ROWS[:2], 2)
    assert page["next_cursor"] is None


@pytest.mark.parametrize("limit", [0, -1, 51, 1.5, True])
def test_invalid_limit_is_rejected(limit):
    with pytest.raises(ValueError):
        list_orders(ROWS, limit)
