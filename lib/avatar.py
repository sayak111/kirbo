import json


AVATAR_SIZE = 16
AVATAR_PALETTE = (
    None,
    (30, 34, 48),
    (239, 190, 145),
    (190, 122, 91),
    (67, 113, 156),
    (235, 111, 91),
    (246, 211, 115),
    (246, 240, 220),
)
DEFAULT_AVATAR = (
    "0000011111000000",
    "0000112222110000",
    "0001222222221000",
    "0012222222222100",
    "0012112211222100",
    "0012112211222100",
    "0012222222222100",
    "0012232222322100",
    "0012222222222100",
    "0001222222221000",
    "0000124442100000",
    "0000144444100000",
    "0001444444410000",
    "0001440404410000",
    "0001140040110000",
    "0000111111000000",
)


def validate_avatar(rows):
    if not isinstance(rows, (list, tuple)) or len(rows) != AVATAR_SIZE:
        raise ValueError("Avatar must contain exactly 16 rows.")

    normalized = []
    allowed_pixels = "01234567"
    for row in rows:
        if not isinstance(row, str) or len(row) != AVATAR_SIZE:
            raise ValueError("Each avatar row must contain exactly 16 pixels.")
        if any(pixel not in allowed_pixels for pixel in row):
            raise ValueError("Avatar pixels must use palette indexes 0 through 7.")
        normalized.append(row)
    return normalized


def decode_avatar(value):
    try:
        rows = json.loads(value) if isinstance(value, str) else value
        return validate_avatar(rows)
    except (TypeError, ValueError, json.JSONDecodeError):
        return list(DEFAULT_AVATAR)