from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

CHECK_PATHS = [
    ROOT / "app.py",
    ROOT / "templates",
    ROOT / "static" / "js",
]

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".json",
    ".html",
    ".css",
}

MOJIBAKE_MARKERS = (
    "Ã©",
    "Ã¨",
    "Ã ",
    "Ãª",
    "Ã®",
    "Ã´",
    "Ã§",
    "Â ",
    "â€™",
    "â€œ",
    "â€",
    "Ð°",
    "Ðµ",
    "Ð¸",
    "Ð¾",
    "Ð½",
    "Ñ€",
    "Ñ‚",
    "ÑÑ",
)


def source_files():
    for path in CHECK_PATHS:
        if path.is_file():
            yield path
            continue

        for file in path.rglob("*"):
            if file.is_file() and file.suffix.lower() in TEXT_EXTENSIONS:
                yield file


def test_source_files_are_valid_utf8_and_not_mojibake():
    problems = []

    for file in source_files():
        try:
            text = file.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            problems.append(f"{file.relative_to(ROOT)}: invalid UTF-8: {exc}")
            continue

        found = [marker for marker in MOJIBAKE_MARKERS if marker in text]

        if found:
            problems.append(
                f"{file.relative_to(ROOT)}: possible mojibake: {found}"
            )

    assert not problems, (
        "\nEncoding safety check failed:\n"
        + "\n".join(problems)
    )