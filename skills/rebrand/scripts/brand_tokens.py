"""Shared helpers for brand token extraction and case/separator variant generation.

Single source of truth for how brand tokens become matching/replacement
variants. Imported by brand-replace.py, artifact-scan.py and inventory.py so
the DRY rule is not violated.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

# Keys that may be present in brand.json's "original"/"target" blocks.
TOKEN_KEYS = ("name", "slug", "org", "domain", "package", "namespace")

def get_version() -> str:
    """Read the package VERSION file."""
    vf = Path(__file__).resolve().parent.parent / "VERSION"
    if vf.exists():
        return vf.read_text(encoding="utf-8").strip()
    return "dev"

# Separators that appear between words in identifiers/names.
SEPARATORS = (" ", "_", "-", ".", "/")


def load_brand(path: Path) -> dict:
    """Load and validate brand.json; raise ValueError on a bad shape."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("brand.json must be a JSON object")
    if "target" not in data or not isinstance(data["target"], dict):
        raise ValueError("brand.json requires a 'target' object")
    if "original" not in data or not isinstance(data["original"], dict):
        raise ValueError("brand.json requires an 'original' object")
    # Schema validation (optional dependency).
    try:
        import jsonschema
        schema_path = Path(__file__).resolve().parent.parent / "templates" / "brand.schema.json"
        if schema_path.exists():
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.validate(data, schema)
    except ImportError:
        pass  # jsonschema not installed; skip
    except Exception as exc:
        raise ValueError(f"brand.json schema validation failed: {exc}") from exc
    return data


def split_words(token: str) -> List[str]:
    """Split a token into words on separators and PascalCase boundaries."""
    pieces = re.split(r"[\s_\-./]+", token)
    words: List[str] = []
    for piece in pieces:
        if not piece:
            continue
        # Split CamelCase / PascalCase runs.
        parts = re.findall(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|\d+", piece)
        if parts:
            words.extend(parts)
        else:
            words.append(piece)
    return [w for w in words if w]


def style(words: List[str], form: str) -> str:
    """Render a word list in one of the common identifier styles."""
    if not words:
        return ""
    low = [w.lower() for w in words]
    cap = [w.capitalize() for w in words]
    if form == "lower":
        return " ".join(low)
    if form == "upper":
        return " ".join(w.upper() for w in words)
    if form == "space":
        return " ".join(words)
    if form == "snake":
        return "_".join(low)
    if form == "kebab":
        return "-".join(low)
    if form == "dot":
        return ".".join(low)
    if form == "slash":
        return "/".join(low)
    if form == "pascal":
        return "".join(cap)
    if form == "camel":
        return low[0] + "".join(cap[1:]) if len(cap) > 1 else low[0]
    if form == "upper_snake":
        return "_".join(w.upper() for w in words)
    if form == "upper_kebab":
        return "-".join(w.upper() for w in words)
    if form == "concat":
        return "".join(low)
    if form == "upper_concat":
        return "".join(w.upper() for w in words)
    raise ValueError(f"unknown style {form!r}")


STYLES = (
    "lower", "upper", "space", "snake", "kebab", "dot", "slash",
    "pascal", "camel", "upper_snake", "upper_kebab", "concat", "upper_concat",
)


def variant_forms(token: str) -> List[str]:
    """All case/separator variants of a single token string."""
    words = split_words(token)
    out: List[str] = []
    seen = set()
    for form in STYLES:
        v = style(words, form)
        if v and v not in seen:
            seen.add(v)
            out.append(v)
    # Always keep the raw token too.
    if token and token not in seen:
        seen.add(token)
        out.append(token)
    return out


def token_pairs(brand: dict) -> List[Tuple[str, str]]:
    """Return (old_variant, new_variant) pairs for every shared token key.

    Sorted by old-variant length descending so longer matches win when
    applying replacements.
    """
    original = brand.get("original", {})
    target = brand.get("target", {})
    pairs: List[Tuple[str, str]] = []
    for key in TOKEN_KEYS:
        if key not in original or key not in target:
            continue
        old_tok = str(original[key]).strip()
        new_tok = str(target[key]).strip()
        if not old_tok or not new_tok or old_tok == new_tok:
            continue
        # Pair variants style-by-style.
        old_forms = variant_forms(old_tok)
        new_forms = variant_forms(new_tok)
        # If word counts match, pair by index; otherwise fall back to raw.
        if len(old_forms) == len(new_forms):
            for o, n in zip(old_forms, new_forms):
                if o != n:
                    pairs.append((o, n))
        else:
            pairs.append((old_tok, new_tok))
    # Deduplicate while preserving order.
    seen = set()
    deduped = []
    for o, n in pairs:
        if (o, n) not in seen:
            seen.add((o, n))
            deduped.append((o, n))
    deduped.sort(key=lambda p: len(p[0]), reverse=True)
    return deduped


def boundary_pattern(old_variant: str) -> str:
    """Build a regex matching old_variant with alphanumeric boundaries."""
    escaped = re.escape(old_variant)
    return rf"(?<![A-Za-z0-9]){escaped}(?![A-Za-z0-9])"


def residual_variants(tokens: Iterable[str]) -> List[str]:
    """Case-insensitive substring forms used for leftover scanning."""
    out = []
    seen = set()
    for t in tokens:
        for v in variant_forms(t):
            low = v.lower()
            if low not in seen:
                seen.add(low)
                out.append(low)
    return out
