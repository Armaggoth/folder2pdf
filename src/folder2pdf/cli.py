#!/usr/bin/env python3
"""Create a PDF from images in a folder, named after the folder."""

from __future__ import annotations

import argparse
import importlib.util
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List

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
        subprocess.run(command, check=True)
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


def maybe_install_command() -> None:
    command_location = shutil.which("folder2pdf")
    if command_location:
        return

    print("Notice: folder2pdf command is not installed on PATH.", file=sys.stderr)
    print("Install this package with: pip install folder2pdf", file=sys.stderr)


def natural_sort_key(text: str) -> List[object]:
    # Sorts filenames like image2 before image10.
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", text)]


def collect_images(folder: Path) -> List[Path]:
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


def find_folders_with_images(root: Path) -> List[Path]:
    folders = []
    for current_root, _, _ in os.walk(root):
        current_folder = Path(current_root)
        if collect_images(current_folder):
            folders.append(current_folder)

    folders.sort(key=lambda p: natural_sort_key(str(p.relative_to(root))))
    return folders


def get_img2pdf_module():
    import img2pdf

    return img2pdf


def create_pdf(images: List[Path], output_pdf: Path) -> None:
    img2pdf = get_img2pdf_module()
    with output_pdf.open("wb") as out_file:
        out_file.write(img2pdf.convert([str(path) for path in images]))


def merge_pdfs(pdf_paths: List[Path], output_pdf: Path) -> bool:
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="folder2pdf",
        description="Create a PDF from all images in a folder.",
        epilog=(
            "Examples:\n"
            "  folder2pdf .\n"
            "  folder2pdf --overwrite .\n"
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
        "-o",
        "--overwrite",
        action="store_true",
        help="Overwrite output PDF if it already exists.",
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
    maybe_install_command()

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

    folder = Path(args.folder).expanduser().resolve()
    if not folder.exists() or not folder.is_dir():
        print(f"Error: folder does not exist or is not a directory: {folder}", file=sys.stderr)
        return 1

    if args.recurse:
        folders = find_folders_with_images(folder)
        if not folders:
            print(
                f"Error: no supported images found in {folder} or its subfolders. "
                f"Supported extensions: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
                file=sys.stderr,
            )
            return 1

        generated_pdfs: List[Path] = []
        for current_folder in folders:
            images = collect_images(current_folder)
            output_pdf = current_folder / f"{current_folder.name}.pdf"

            if output_pdf.exists() and not args.overwrite:
                print(
                    f"Error: output already exists: {output_pdf}. Use --overwrite to replace it.",
                    file=sys.stderr,
                )
                return 1

            try:
                create_pdf(images, output_pdf)
            except Exception as exc:
                print(f"Error: failed to create PDF for {current_folder}: {exc}", file=sys.stderr)
                return 1

            generated_pdfs.append(output_pdf)
            print(f"Created: {output_pdf}")
            print(f"Pages: {len(images)}")

        if args.merge:
            merge_output = Path.cwd().resolve() / f"{Path.cwd().resolve().name}_merged.pdf"
            if merge_output.exists() and not args.overwrite:
                print(
                    f"Error: merged output already exists: {merge_output}. Use --overwrite to replace it.",
                    file=sys.stderr,
                )
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

    if output_pdf.exists() and not args.overwrite:
        print(
            f"Error: output already exists: {output_pdf}. Use --overwrite to replace it.",
            file=sys.stderr,
        )
        return 1

    try:
        create_pdf(images, output_pdf)
    except Exception as exc:
        print(f"Error: failed to create PDF: {exc}", file=sys.stderr)
        return 1

    print(f"Created: {output_pdf}")
    print(f"Pages: {len(images)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
