from decimal import Decimal
from ministore.pricing import calculate_total


def test_single_unit_rounding_contract():
    result = calculate_total([{"unit_price": "19.95", "quantity": 1}], "0.10", "0.00")
    assert result["subtotal"] == Decimal("17.96")


def test_multiple_units_round_after_line_discount():
    result = calculate_total([{"unit_price": "19.95", "quantity": 3}], "0.10", "0.00")
    assert result["subtotal"] == Decimal("53.87")
