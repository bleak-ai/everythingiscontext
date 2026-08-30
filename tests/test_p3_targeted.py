"""Targeted tests for parse_github_url and secrets.scrub edge cases."""

import pytest

from gcontext import registry
from gcontext import secrets as secrets_mod


# --- parse_github_url (item 70b) ---


class TestParseGithubUrl:
    def test_plain_repo(self):
        owner_repo, ref, subpath = registry.parse_github_url(
            "https://github.com/bleak-ai/agents"
        )
        assert owner_repo == "bleak-ai/agents"
        assert ref == "main"
        assert subpath == ""

    def test_branch_ref(self):
        owner_repo, ref, subpath = registry.parse_github_url(
            "https://github.com/bleak-ai/agents/tree/develop"
        )
        assert owner_repo == "bleak-ai/agents"
        assert ref == "develop"
        assert subpath == ""

    def test_tag_ref(self):
        owner_repo, ref, subpath = registry.parse_github_url(
            "https://github.com/bleak-ai/agents/tree/v1.2.3"
        )
        assert owner_repo == "bleak-ai/agents"
        assert ref == "v1.2.3"
        assert subpath == ""

    def test_ref_with_subpath(self):
        owner_repo, ref, subpath = registry.parse_github_url(
            "https://github.com/bleak-ai/agents/tree/main/browser-recipes"
        )
        assert owner_repo == "bleak-ai/agents"
        assert ref == "main"
        assert subpath == "browser-recipes"

    def test_deep_subpath(self):
        owner_repo, ref, subpath = registry.parse_github_url(
            "https://github.com/owner/repo/tree/main/a/b/c"
        )
        assert owner_repo == "owner/repo"
        assert ref == "main"
        assert subpath == "a/b/c"

    def test_bare_github_prefix(self):
        owner_repo, ref, subpath = registry.parse_github_url(
            "github.com/bleak-ai/agents"
        )
        assert owner_repo == "bleak-ai/agents"
        assert ref == "main"
        assert subpath == ""

    def test_invalid_url_raises(self):
        with pytest.raises(registry.RegistryError):
            registry.parse_github_url("https://github.com/only-owner")


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
