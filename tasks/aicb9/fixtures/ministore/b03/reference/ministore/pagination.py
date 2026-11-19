"""Reference pagination contract for B03."""


def encode_cursor(created_at, identifier):
    return f"{int(created_at)}|{identifier}"


def decode_cursor(cursor):
    if cursor is None:
        return None
    created_at, identifier = cursor.split("|", 1)
    return int(created_at), identifier


def list_orders(rows, limit, cursor=None):
    if type(limit) is not int or not 1 <= limit <= 50:
        raise ValueError("limit must be an integer between 1 and 50")
    ordered = sorted(rows, key=lambda row: (int(row["created_at"]), str(row["id"])), reverse=True)
    boundary = decode_cursor(cursor)
    if boundary is not None:
        ordered = [row for row in ordered if (int(row["created_at"]), str(row["id"])) < boundary]
    page = ordered[:limit]
    has_more = len(ordered) > limit
    next_cursor = encode_cursor(page[-1]["created_at"], page[-1]["id"]) if has_more and page else None
    return {"items": page, "next_cursor": next_cursor}
