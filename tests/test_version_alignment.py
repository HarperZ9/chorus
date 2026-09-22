"""The declared version must agree everywhere it is written down.

chorus declares its version twice: once in ``pyproject.toml`` for the built
distribution and once as ``chorus.__version__`` for anything that asks the
running package what it is. Nothing previously tied the two together, so a
release could ship 0.3.1 while the module reported 0.3.0 and every test still
passed. The release workflow checks the git tag against ``pyproject.toml`` and
would not have caught it either, because it never reads the module.
"""
from __future__ import annotations

import pathlib
import tomllib

import chorus


def _declared_version() -> str:
    root = pathlib.Path(__file__).resolve().parents[1]
    with (root / "pyproject.toml").open("rb") as handle:
        return tomllib.load(handle)["project"]["version"]


def test_module_version_matches_the_declared_distribution_version():
    assert chorus.__version__ == _declared_version()


def test_the_changelog_has_an_entry_for_the_declared_version():
    root = pathlib.Path(__file__).resolve().parents[1]
    changelog = (root / "CHANGELOG.md").read_text(encoding="utf-8")
    version = _declared_version()
    assert f"## {version}" in changelog, (
        f"CHANGELOG.md has no '## {version}' heading, so the release would ship "
        "without saying what changed")
