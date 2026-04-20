"""Tests for ``mayutils.export.images``."""

from __future__ import annotations

from pathlib import Path

from mayutils.export import OUTPUT_FOLDER
from mayutils.export.images import IMAGES_FOLDER


def test_images_folder_is_path() -> None:
    """:data:`IMAGES_FOLDER` is a :class:`pathlib.Path`."""
    assert isinstance(IMAGES_FOLDER, Path)


def test_images_folder_nested_under_output_folder() -> None:
    """:data:`IMAGES_FOLDER` lives directly beneath :data:`OUTPUT_FOLDER`."""
    assert IMAGES_FOLDER.parent == OUTPUT_FOLDER
    assert IMAGES_FOLDER.name == "Images"
