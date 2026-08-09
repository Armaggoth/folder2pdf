"""Tests for folder2pdf CLI — one test per use case."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image
from pypdf import PdfReader

from folder2pdf.cli import (
    SUPPORTED_EXTENSIONS,
    collect_images,
    main,
    natural_sort_key,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(args: list[str]) -> int:
    """Call main() with the given CLI args and return its exit code."""
    with patch("sys.argv", ["folder2pdf"] + args):
        return main()


def _make_images(folder: Path, count: int) -> None:
    """Create `count` tiny synthetic PNG images in folder, naturally sorted by name."""
    for i in range(count):
        Image.new("RGB", (10, 10), color=(i * 20, 100, 200)).save(
            folder / f"image{i:02d}.png"
        )


# ---------------------------------------------------------------------------
# Single folder
# ---------------------------------------------------------------------------

def test_single_folder_creates_pdf(tmp_path):
    folder = tmp_path / "slides"
    folder.mkdir()
    _make_images(folder, 6)

    assert _run([str(folder)]) == 0
    assert (folder / "slides.pdf").exists()


def test_single_folder_pdf_page_count_matches_images(tmp_path):
    folder = tmp_path / "slides"
    folder.mkdir()
    _make_images(folder, 6)

    _run([str(folder)])

    expected = len(collect_images(folder))
    assert len(PdfReader(folder / "slides.pdf").pages) == expected


def test_single_folder_no_images_returns_error(tmp_path):
    assert _run([str(tmp_path)]) == 1


def test_nonexistent_folder_returns_error(tmp_path):
    assert _run([str(tmp_path / "ghost")]) == 1


# ---------------------------------------------------------------------------
# Overwrite behaviour
# ---------------------------------------------------------------------------

def test_existing_pdf_without_force_aborts(tmp_path):
    folder = tmp_path / "slides"
    folder.mkdir()
    _make_images(folder, 6)
    (folder / "slides.pdf").write_bytes(b"%PDF-1.4 stub")

    # stdin is not a TTY in tests → ask_yes_no returns False → abort
    assert _run([str(folder)]) == 1


def test_existing_pdf_with_force_overwrites(tmp_path):
    folder = tmp_path / "slides"
    folder.mkdir()
    _make_images(folder, 6)
    stub = folder / "slides.pdf"
    stub.write_bytes(b"%PDF-1.4 stub")
    original_size = stub.stat().st_size

    assert _run(["--force", str(folder)]) == 0
    assert stub.stat().st_size > original_size  # real PDF replaced the stub


# ---------------------------------------------------------------------------
# Recurse
# ---------------------------------------------------------------------------

def test_recurse_creates_pdf_in_each_subfolder(tmp_path):
    sub_a = tmp_path / "00 Module A"
    sub_b = tmp_path / "01 Module B"
    sub_a.mkdir()
    sub_b.mkdir()
    _make_images(sub_a, 6)
    _make_images(sub_b, 4)

    assert _run(["--recurse", str(tmp_path)]) == 0
    assert (sub_a / "00 Module A.pdf").exists()
    assert (sub_b / "01 Module B.pdf").exists()


def test_recurse_no_images_anywhere_returns_error(tmp_path):
    (tmp_path / "empty").mkdir()
    assert _run(["--recurse", str(tmp_path)]) == 1


def test_recurse_existing_pdf_without_force_aborts(tmp_path):
    sub_a = tmp_path / "00 Module A"
    sub_a.mkdir()
    _make_images(sub_a, 6)
    (sub_a / "00 Module A.pdf").write_bytes(b"%PDF-1.4 stub")

    assert _run(["--recurse", str(tmp_path)]) == 1


# ---------------------------------------------------------------------------
# Recurse + merge
# ---------------------------------------------------------------------------

def test_recurse_merge_creates_merged_pdf(tmp_path, monkeypatch):
    sub_a = tmp_path / "00 Module A"
    sub_b = tmp_path / "01 Module B"
    sub_a.mkdir()
    sub_b.mkdir()
    _make_images(sub_a, 6)
    _make_images(sub_b, 4)
    monkeypatch.chdir(tmp_path)  # merged PDF lands in cwd

    assert _run(["--recurse", "--merge", str(tmp_path)]) == 0
    assert (tmp_path / f"{tmp_path.name}_merged.pdf").exists()


def test_recurse_merge_page_count_is_sum_of_all_folders(tmp_path, monkeypatch):
    sub_a = tmp_path / "00 Module A"
    sub_b = tmp_path / "01 Module B"
    sub_a.mkdir()
    sub_b.mkdir()
    _make_images(sub_a, 6)
    _make_images(sub_b, 4)
    monkeypatch.chdir(tmp_path)

    _run(["--recurse", "--merge", str(tmp_path)])

    expected = 6 + 4
    merged = tmp_path / f"{tmp_path.name}_merged.pdf"
    assert len(PdfReader(merged).pages) == expected


def test_merge_without_recurse_exits_nonzero():
    # argparse calls sys.exit(2) when validation fails
    with pytest.raises(SystemExit) as exc_info:
        _run(["--merge", "."])
    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def test_help_subcommand_exits_zero(tmp_path):
    assert _run(["help"]) == 0


# ---------------------------------------------------------------------------
# Natural sort
# ---------------------------------------------------------------------------

def test_natural_sort_orders_numerically():
    names = ["image10.png", "image2.png", "image1.png"]
    assert sorted(names, key=natural_sort_key) == [
        "image1.png",
        "image2.png",
        "image10.png",
    ]


# ---------------------------------------------------------------------------
# Hidden files
# ---------------------------------------------------------------------------

def test_hidden_files_are_excluded(tmp_path):
    folder = tmp_path / "slides"
    folder.mkdir()
    _make_images(folder, 3)
    (folder / ".hidden.png").write_bytes(b"fake image data")

    images = collect_images(folder)
    assert not any(p.name.startswith(".") for p in images)
