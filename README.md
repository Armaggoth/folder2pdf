# folder2pdf

Create a PDF from images in a folder, with the PDF name matching the folder name.

## Features

- Natural file ordering (`image2` before `image10`)
- In-place output (`<folder>/<folder>.pdf`)
- Optional recursion (`--recurse`)
- Optional merged PDF when recursing (`--merge`)
- Safety checks for overwrite and missing dependencies

## Install

```bash
pip install folder2pdf
```

For local development:

```bash
pip install -e .
```

## Usage

```bash
folder2pdf .
folder2pdf --overwrite .
folder2pdf --recurse .
folder2pdf --recurse --merge .
folder2pdf "/path/to/folder"
folder2pdf help
```

## Notes

- `--merge` only works with `--recurse`.
- Merged output is written to the current working directory.
- Supported extensions: `.jpg`, `.jpeg`, `.png`, `.tif`, `.tiff`, `.bmp`, `.gif`, `.webp`.

## Build and publish

```bash
python -m pip install --upgrade build twine
python -m build
python -m twine upload dist/*
```
