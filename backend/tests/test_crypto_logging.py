from app.core.crypto import PasswordEncryptor
from app.core.logging import redact_mapping, redact_text


def test_password_encryptor_round_trip():
    encryptor = PasswordEncryptor("test-secret")

    encrypted = encryptor.encrypt("library-password")

    assert encrypted != "library-password"
    assert encryptor.decrypt(encrypted) == "library-password"


def test_redact_text_masks_sensitive_values():
    text = "Authorization: Bearer abc\npassword=secret token: value"

    redacted = redact_text(text)

    assert "Bearer abc" not in redacted
    assert "secret" not in redacted
    assert "Authorization: ***" in redacted
    assert "password=***" in redacted


def test_redact_mapping_masks_nested_sensitive_keys():
    redacted = redact_mapping(
        {
            "username": "alice",
            "password": "secret",
            "headers": {"Cookie": "session=abc"},
        }
    )

    assert redacted["username"] == "alice"
    assert redacted["password"] == "***"
    assert redacted["headers"]["Cookie"] == "***"
