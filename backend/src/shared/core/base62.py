import string

from hashids import Hashids

BASE62_ALPHABET = string.ascii_letters + string.digits  # a-zA-Z0-9 (len 62)


def encode_base62(num: int) -> str:
    chars = []
    while num > 0:
        num, rem = divmod(num, 62)
        chars.append(BASE62_ALPHABET[rem])
    return "".join(reversed(chars)).rjust(7, "0")


def hashid_encode(seq_value: int, salt: str, min_length: int = 7) -> str:
    hid = Hashids(salt=salt, min_length=min_length)
    return hid.encode(seq_value)  # type: ignore[no-any-return]
