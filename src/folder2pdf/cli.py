#!/usr/bin/env python3
"""Create a PDF from images in a folder, named after the folder."""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

SUPPORTED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".bmp",
    ".gif",
    ".webp",
}


def ask_yes_no(question: str) -> bool:
    if not sys.stdin.isatty():
        return False
    answer = input(f"{question} [y/N]: ").strip().lower()
    return answer in {"y", "yes"}


def install_python_package(package_name: str) -> bool:
    command = [sys.executable, "-m", "pip", "install", package_name]
    try:
        subprocess.run(command, check=True, capture_output=True)
        return True
    except subprocess.CalledProcessError:
        return False


def ensure_dependency(module_name: str, package_name: str, reason: str) -> bool:
    if importlib.util.find_spec(module_name):
        return True

    print(f"Dependency missing: {package_name} ({reason}).", file=sys.stderr)
    if ask_yes_no(f"Install {package_name} automatically now?"):
        if install_python_package(package_name) and importlib.util.find_spec(module_name):
            return True
        print(f"Error: failed to install {package_name}.", file=sys.stderr)
        return False

    print(
        f"Install manually with: {sys.executable} -m pip install {package_name}",
        file=sys.stderr,
    )
    return False


def natural_sort_key(text: str) -> list[object]:
    # Sorts filenames like image2 before image10.
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def collect_images(folder: Path) -> list[Path]:
    images = []
    for item in folder.iterdir():
        if not item.is_file():
            continue
        if item.name.startswith("."):
            continue
        if item.suffix.lower() in SUPPORTED_EXTENSIONS:
            images.append(item)
    images.sort(key=lambda p: natural_sort_key(p.name))
    return images


def find_folders_with_images(root: Path) -> list[tuple[Path, list[Path]]]:
    results = []
    for dirpath, _, _ in root.walk():
        images = collect_images(dirpath)
        if images:
            results.append((dirpath, images))
    results.sort(key=lambda pair: natural_sort_key(str(pair[0].relative_to(root))))
    return results


def create_pdf(images: list[Path], output_pdf: Path) -> None:
    import img2pdf
    data = img2pdf.convert([str(path) for path in images])
    if data is None:
        raise ValueError("img2pdf produced no output")
    with output_pdf.open("wb") as out_file:
        out_file.write(data)


def merge_pdfs(pdf_paths: list[Path], output_pdf: Path) -> bool:
    if not ensure_dependency("pypdf", "pypdf", "required for --merge"):
        return False

    from pypdf import PdfWriter

    writer = PdfWriter()
    try:
        for pdf_path in pdf_paths:
            writer.append(str(pdf_path))
        with output_pdf.open("wb") as out_file:
            writer.write(out_file)
    finally:
        writer.close()

    return True


def _confirm_overwrite(path: Path, force: bool) -> bool:
    """Return True if it's safe to write to path (doesn't exist, forced, or user confirmed)."""
    if not path.exists() or force:
        return True
    return ask_yes_no(f"Output already exists: {path}. Overwrite?")


def _print_created(output_pdf: Path, images: list[Path]) -> None:
    print(f"Created: {output_pdf}")
    print(f"Pages: {len(images)}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="folder2pdf",
        description="Create a PDF from all images in a folder.",
        epilog=(
            "Examples:\n"
            "  folder2pdf .\n"
            "  folder2pdf --force .\n"
            "  folder2pdf --recurse .\n"
            "  folder2pdf --recurse --merge .\n"
            "  folder2pdf \"/path/to/folder\"\n\n"
            "Notes:\n"
            "  --merge only works together with --recurse.\n"
            "  Merged output is written to the current working directory."
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "folder",
        help="Path to folder containing images.",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Overwrite existing PDFs without prompting.",
    )
    parser.add_argument(
        "-r",
        "--recurse",
        action="store_true",
        help="Process this folder and all nested subfolders.",
    )
    parser.add_argument(
        "-m",
        "--merge",
        action="store_true",
        help="Merge all generated folder PDFs into one PDF in the current directory (requires --recurse).",
    )
    return parser


def main() -> int:
    if not ensure_dependency("img2pdf", "img2pdf", "required for image to PDF conversion"):
        return 2

    parser = build_parser()
    # Support `folder2pdf help` in addition to argparse's `-h/--help`.
    if len(sys.argv) >= 2 and sys.argv[1].strip().lower() == "help":
        parser.print_help()
        return 0
    args = parser.parse_args()

    if args.merge and not args.recurse:
        parser.error("--merge can only be used together with --recurse")

    force: bool = args.force

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        print(f"Error: folder does not exist or is not a directory: {folder}", file=sys.stderr)
        return 1

    if args.recurse:
        folder_image_pairs = find_folders_with_images(folder)
        if not folder_image_pairs:
            print(
                f"Error: no supported images found in {folder} or its subfolders. "
                f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                file=sys.stderr,
            )
            return 1

        generated_pdfs: list[Path] = []
        for current_folder, images in folder_image_pairs:
            output_pdf = current_folder / f"{current_folder.name}.pdf"

            if not _confirm_overwrite(output_pdf, force):
                return 1

            try:
                create_pdf(images, output_pdf)
            except Exception as exc:
                print(f"Error: failed to create PDF for {current_folder}: {exc}", file=sys.stderr)
                return 1

            generated_pdfs.append(output_pdf)
            _print_created(output_pdf, images)

        if args.merge:
            cwd = Path.cwd()
            merge_output = cwd / f"{cwd.name}_merged.pdf"

            if not _confirm_overwrite(merge_output, force):
                return 1

            if not merge_pdfs(generated_pdfs, merge_output):
                return 1

            print(f"Merged: {merge_output}")
            print(f"Merged files: {len(generated_pdfs)}")

        return 0

    images = collect_images(folder)
    if not images:
        print(
            f"Error: no supported images found in {folder}. "
            f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            file=sys.stderr,
        )
        return 1

    output_pdf = folder / f"{folder.name}.pdf"

    if not _confirm_overwrite(output_pdf, force):
        return 1

    try:
        create_pdf(images, output_pdf)
    except Exception as exc:
        print(f"Error: failed to create PDF: {exc}", file=sys.stderr)
        return 1

    _print_created(output_pdf, images)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
