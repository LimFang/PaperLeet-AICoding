"""Mutant: accepts zero limit rather than rejecting invalid input."""
def encode_cursor(created_at, identifier): return f"{int(created_at)}|{identifier}"
def decode_cursor(cursor):
    if cursor is None: return None
    a, b = cursor.split("|", 1); return int(a), b
def list_orders(rows, limit, cursor=None):
    if type(limit) is not int or not 0 <= limit <= 50: raise ValueError("bad limit")
    ordered = sorted(rows, key=lambda r: (int(r["created_at"]), str(r["id"])), reverse=True)
    boundary = decode_cursor(cursor)
    if boundary is not None: ordered = [r for r in ordered if (int(r["created_at"]), str(r["id"])) < boundary]
    page = ordered[:limit]; more = len(ordered) > limit
    return {"items": page, "next_cursor": encode_cursor(page[-1]["created_at"], page[-1]["id"]) if more and page else None}
