import pytest

from src.utils.base62 import BASE62_ALPHABET, encode_base62, hashid_encode


class TestEncodeBase62:
    def test_encode_zero(self):
        assert encode_base62(0) == "0000000"

    def test_encode_one(self):
        result = encode_base62(1)
        assert len(result) == 7
        assert result == "000000b"

    def test_encode_small_number(self):
        result = encode_base62(61)
        assert len(result) == 7
        assert result == "0000009"

    def test_encode_62(self):
        result = encode_base62(62)
        assert len(result) == 7
        assert result == "00000ba"

    def test_encode_large_number(self):
        result = encode_base62(3844)
        assert len(result) == 7

    def test_encode_always_returns_7_chars(self):
        for val in [0, 1, 10, 100, 1000, 1000000, 56800235583]:
            result = encode_base62(val)
            assert len(result) == 7

    def test_encode_pads_with_zero_character(self):
        val = 123456789
        encoded = encode_base62(val)
        assert len(encoded) == 7
        assert all(c in BASE62_ALPHABET for c in encoded)

    def test_encoding_uses_correct_characters(self):
        for val in range(0, 200):
            result = encode_base62(val)
            assert all(c in BASE62_ALPHABET for c in result)


class TestHashidEncode:
    def test_encode_with_salt(self):
        result = hashid_encode(1, "test-salt")
        assert isinstance(result, str)
        assert len(result) >= 7

    def test_different_salts_produce_different_results(self):
        r1 = hashid_encode(42, "salt-a")
        r2 = hashid_encode(42, "salt-b")
        assert r1 != r2

    def test_different_values_produce_different_results(self):
        r1 = hashid_encode(1, "salt")
        r2 = hashid_encode(2, "salt")
        assert r1 != r2

    def test_same_input_produces_same_output(self):
        r1 = hashid_encode(100, "consistent-salt")
        r2 = hashid_encode(100, "consistent-salt")
        assert r1 == r2

    def test_encode_zero(self):
        result = hashid_encode(0, "salt")
        assert isinstance(result, str)
        assert len(result) >= 7

    def test_encode_large_value(self):
        result = hashid_encode(999999999, "salt")
        assert isinstance(result, str)
        assert len(result) >= 7

    def test_min_length_parameter(self):
        result = hashid_encode(1, "salt", min_length=12)
        assert len(result) >= 12

    def test_encode_returns_only_alphanumeric(self):
        result = hashid_encode(42, "salt")
        assert result.isalnum()

    def test_encode_with_empty_salt(self):
        result = hashid_encode(1, "")
        assert isinstance(result, str)
        assert len(result) >= 7


class TestBase62Alphabet:
    def test_alphabet_length(self):
        assert len(BASE62_ALPHABET) == 62

    def test_alphabet_contains_all_letters_and_digits(self):
        import string
        assert BASE62_ALPHABET == string.ascii_letters + string.digits

    def test_alphabet_no_duplicates(self):
        assert len(set(BASE62_ALPHABET)) == 62

    def test_alphabet_lowercase_first(self):
        assert BASE62_ALPHABET.startswith("abcdefghijklmnopqrstuvwxyz")
