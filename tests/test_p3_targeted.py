"""Targeted tests for secrets.scrub edge cases."""

from gcontext import secrets as secrets_mod


# --- secrets.scrub edge cases (item 70c) ---


class TestScrubEdgeCases:
    def test_short_values_not_scrubbed(self):
        """Values with 3 or fewer characters must not be scrubbed."""
        text = "key=abc and x=AB"
        result = secrets_mod.scrub(text, {"SHORT": "abc", "TINY": "AB"})
        assert result == text

    def test_four_char_value_is_scrubbed(self):
        """Values with more than 3 characters must be scrubbed."""
        text = "token is abcd in the output"
        result = secrets_mod.scrub(text, {"TOKEN": "abcd"})
        assert "abcd" not in result
        assert "***" in result

    def test_empty_value_not_scrubbed(self):
        """Empty values must not cause errors or false matches."""
        text = "nothing to hide"
        result = secrets_mod.scrub(text, {"EMPTY": ""})
        assert result == text

    def test_value_inside_url_is_scrubbed(self):
        """A secret that appears inside a URL must be scrubbed."""
        secret = "sk-verysecret"
        text = f"https://api.example.com/v1?key={secret}&format=json"
        result = secrets_mod.scrub(text, {"API_KEY": secret})
        assert secret not in result
        assert "***" in result

    def test_multiple_occurrences_scrubbed(self):
        """All occurrences of a secret must be replaced."""
        secret = "mysecretvalue"
        text = f"first {secret} and second {secret}"
        result = secrets_mod.scrub(text, {"KEY": secret})
        assert secret not in result
        assert result.count("***") == 2
