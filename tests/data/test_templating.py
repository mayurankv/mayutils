"""Tests for Jinja-based query template rendering."""

import warnings
from pathlib import Path

import pytest
from jinja2.exceptions import UndefinedError

from mayutils.data.queries.templating import TemplateStyleWarning, render_template


def test_render_template_substitutes_variables() -> None:
    """``{{ name }}`` placeholders are substituted from *jinja_kwargs*."""
    assert render_template("SELECT * FROM {{ table }}", jinja_kwargs={"table": "loans"}) == "SELECT * FROM loans"


def test_render_template_defaults_to_no_substitutions() -> None:
    """Omitting *jinja_kwargs* renders static templates verbatim."""
    assert render_template("SELECT 1") == "SELECT 1"


def test_render_template_supports_loops() -> None:
    """Jinja control flow expands sequence values into SQL fragments."""
    rendered = render_template(
        "SELECT * FROM loans WHERE product IN ({% for p in products %}'{{ p }}'{% if not loop.last %}, {% endif %}{% endfor %})",
        jinja_kwargs={"products": ["personal", "topup"]},
    )
    assert rendered == "SELECT * FROM loans WHERE product IN ('personal', 'topup')"


def test_render_template_supports_conditionals() -> None:
    """``{% if %}`` blocks render conditionally."""
    template = "SELECT * FROM loans{% if region %} WHERE region = '{{ region }}'{% endif %}"
    assert render_template(template, jinja_kwargs={"region": "London"}) == "SELECT * FROM loans WHERE region = 'London'"
    assert render_template(template, jinja_kwargs={"region": None}) == "SELECT * FROM loans"


def test_render_template_includes_from_queries_folders(
    tmp_path: Path,
) -> None:
    """``{% include %}`` resolves templates against *queries_folders*."""
    (tmp_path / "filters.sql").write_text("WHERE dt >= '{{ start }}'", encoding="utf-8")
    rendered = render_template(
        "SELECT * FROM loans {% include 'filters.sql' %}",
        queries_folders=(tmp_path,),
        jinja_kwargs={"start": "2026-01-01"},
    )
    assert rendered == "SELECT * FROM loans WHERE dt >= '2026-01-01'"


def test_render_template_missing_variable_raises() -> None:
    """StrictUndefined surfaces missing kwargs as UndefinedError."""
    with pytest.raises(UndefinedError):
        render_template("SELECT * FROM {{ table }}")


def test_render_template_warns_on_legacy_placeholders() -> None:
    """Surviving ``{kwarg}`` text for a passed key triggers TemplateStyleWarning."""
    with pytest.warns(TemplateStyleWarning):
        rendered = render_template("SELECT * FROM {table}", jinja_kwargs={"table": "loans"})
    assert rendered == "SELECT * FROM {table}"


def test_render_template_no_warning_for_unrelated_braces() -> None:
    """Brace text not matching any key renders silently."""
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert render_template("SELECT '{json}' FROM t", jinja_kwargs={"limit": 1}) == "SELECT '{json}' FROM t"
