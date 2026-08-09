# folder2pdf — Agent Instructions

A single-module Python CLI that converts image folders to PDFs. All logic lives in [`src/folder2pdf/cli.py`](src/folder2pdf/cli.py).

## Dev setup

```bash
pip install -e .          # installs the `folder2pdf` command from source
```

Dependencies: `img2pdf` (image→PDF), `pypdf` (merging). Both are in `pyproject.toml` and installed automatically by the editable install.

## Build & publish

```bash
python -m build
python -m twine upload dist/*
```

## Architecture

The entire tool is one file (`cli.py`). Key sections:

| Function | Purpose |
|---|---|
| `collect_images(folder)` | Lists supported images in a folder, natural-sorted |
| `find_folders_with_images(root)` | Walks subdirectories for `--recurse` |
| `create_pdf(images, output_pdf)` | Converts a list of images to a PDF via `img2pdf` |
| `merge_pdfs(pdf_paths, output_pdf)` | Merges per-folder PDFs via `pypdf` (requires `--merge --recurse`) |
| `ensure_dependency(...)` | Lazy dependency check; offers auto-install interactively |
| `main()` | Entry point; wired via `[project.scripts]` in `pyproject.toml` |

## Key conventions

- **Supported extensions** are centralised in `SUPPORTED_EXTENSIONS` (set of lowercase suffixes). Add new formats there only.
- **Natural sort** (`natural_sort_key`) keeps `image2` before `image10`; always use it when ordering filenames.
- **Output location**: per-folder PDF is written as `<folder>/<folder_name>.pdf` (in-place, not in cwd).
- **Merged output** goes to cwd (not inside any subfolder); `--merge` is only valid with `--recurse`.
- **Dependency loading** for `img2pdf` is deferred via `get_img2pdf_module()` to allow the CLI to report a friendly error before importing.
- Hidden files (names starting with `.`) are skipped in `collect_images`.

## No tests yet

There is no test suite. If adding tests, place them under `tests/` and use `pytest`.
