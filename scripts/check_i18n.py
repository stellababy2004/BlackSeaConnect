"""Validate translations used by BlackSea Connect's multilingual UI."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
I18N_DIR = ROOT / "static" / "js" / "i18n"
LANGUAGES = ("bg", "en", "fr", "ru")
TEMPLATE_NAMESPACES = {
    "templates/index.html": ("home", "common"),
    "templates/owners_request_service.html": ("ownersRequestService", "owners", "common"),
    "templates/owners_dashboard.html": ("ownersDashboard", "owners", "common"),
}
KEY_PATTERNS = (
    re.compile(r'data-i18n(?:-html)?="([^"]+)"'),
    re.compile(r'data-i18n-attr="[^"]*?:([^";]+)'),
    re.compile(r"public_i18n\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]"),
)
DYNAMIC_HOME_KEY_PATTERN = re.compile(
    r"(?:propertyKey|cityKey|ownerKey|statusKey|testimonialQuoteKey|testimonialCopyKey)\s*:\s*['\"]([^'\"]+)['\"]"
)
SLIDES_PATTERN = re.compile(r"const slides\s*=\s*\[(.*?)\];", re.DOTALL)
SUSPICIOUS_SLIDE_TEXT = re.compile(
    r"[А-Яа-яЁё]{3,}|(?:\b(?:the|your|property|guest|work|photos)\b.*[.!?])|"
    r"(?:\b(?:votre|propriété|travail|photos|voyageur)\b.*[.!?])",
    re.IGNORECASE,
)


class DuplicateKeyError(ValueError):
    pass


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(key)
        result[key] = value
    return result


def load_modules():
    modules = {}
    errors = []
    for path in sorted(I18N_DIR.glob("*.js")):
        if path.name == "index.js":
            continue
        source = path.read_text(encoding="utf-8")
        marker = re.search(r'window\.BlackSeaI18NModules\["([^"]+)"\]\s*=\s*', source)
        if not marker:
            continue
        namespace = marker.group(1)
        start = source.find("{", marker.end())
        end = source.rfind("};")
        try:
            payload = json.loads(source[start : end + 1], object_pairs_hook=_unique_object)
        except (json.JSONDecodeError, DuplicateKeyError) as exc:
            errors.append(f"{path.relative_to(ROOT)}: invalid or duplicate JSON key: {exc}")
            continue
        modules[namespace] = payload
    return modules, errors


def collect_template_keys(path):
    source = path.read_text(encoding="utf-8")
    keys = set()
    explicit = set()
    for pattern in KEY_PATTERNS[:2]:
        keys.update(match.group(1).strip() for match in pattern.finditer(source))
    for match in KEY_PATTERNS[2].finditer(source):
        explicit.add((match.group(1), match.group(2)))
    return keys, explicit


def validate():
    modules, errors = load_modules()
    checked = set()
    for template_name, candidates in TEMPLATE_NAMESPACES.items():
        path = ROOT / template_name
        keys, explicit = collect_template_keys(path)
        for namespace, key in explicit:
            if (
                namespace in modules
                and any(key in modules[namespace].get(lang, {}).get(namespace, {}) for lang in LANGUAGES)
            ):
                checked.add((namespace, key, template_name))
        for key in keys:
            owners = [
                namespace
                for namespace in candidates
                if namespace in modules
                and any(key in modules[namespace].get(lang, {}).get(namespace, {}) for lang in LANGUAGES)
            ]
            if not owners:
                continue
            checked.add((owners[0], key, template_name))

    homepage_source = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    for key in DYNAMIC_HOME_KEY_PATTERN.findall(homepage_source):
        checked.add(("home", key, "templates/index.html (dynamic carousel)"))
    slides_match = SLIDES_PATTERN.search(homepage_source)
    if not slides_match:
        errors.append("templates/index.html: carousel slide dataset not found")
    else:
        slide_source = slides_match.group(1)
        if SUSPICIOUS_SLIDE_TEXT.search(slide_source):
            errors.append(
                "templates/index.html: suspicious localized sentence in carousel slide dataset; use translation keys"
            )
    if "`n" in homepage_source:
        errors.append("templates/index.html: literal `n template artifact found")

    for namespace, key, template_name in sorted(checked):
        module = modules.get(namespace)
        if not module:
            errors.append(f"{template_name}: missing namespace {namespace!r} for key {key!r}")
            continue
        for lang in LANGUAGES:
            dictionary = module.get(lang, {}).get(namespace, {})
            if key not in dictionary:
                errors.append(f"{lang}: missing {namespace}.{key} (used by {template_name})")
            elif not isinstance(dictionary[key], str) or not dictionary[key].strip():
                errors.append(f"{lang}: empty {namespace}.{key} (used by {template_name})")

    return errors, len(checked), len(modules)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    errors, checked, namespaces = validate()
    print(f"Loaded {namespaces} translation namespaces; checked {checked} visible key bindings.")
    if errors:
        print(f"i18n validation failed with {len(errors)} issue(s):")
        for error in errors:
            print(f"- {error}")
        return 1
    print("All active translations are complete for bg, en, fr, and ru.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
