"""Intentionally buggy pricing implementation for AICB-9 B01."""
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")


def calculate_total(lines, discount_rate, tax_rate):
    """Return subtotal, tax, and total for a list of order lines.

    Bug: rounds each discounted unit price before multiplying by quantity.
    The declared contract requires rounding after computing the discounted
    line subtotal.
    """
    discount_rate = Decimal(str(discount_rate))
    tax_rate = Decimal(str(tax_rate))
    subtotal = Decimal("0.00")
    for line in lines:
        unit_price = Decimal(str(line["unit_price"]))
        quantity = int(line["quantity"])
        discounted_unit = (unit_price * (Decimal("1") - discount_rate)).quantize(CENT, rounding=ROUND_HALF_UP)
        subtotal += discounted_unit * quantity
    tax = (subtotal * tax_rate).quantize(CENT, rounding=ROUND_HALF_UP)
    total = subtotal + tax
    return {"subtotal": subtotal, "tax": tax, "total": total}
