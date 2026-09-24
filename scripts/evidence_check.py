#!/usr/bin/env python3
"""Evidence-boundary checks for generated Xiaohongshu notes."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List, Optional


def validate_content(content: Dict, pack: Dict) -> Dict:
    text = " ".join(str(content.get(key, "")) for key in ("xhs_title", "xhs_content"))
    abstract = " ".join(str(claim.get("evidence", "")) for claim in pack.get("claims", []))
    source_numbers = set(pack.get("numbers", []))
    mentioned_numbers = set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?", text))
    unsupported_numbers = sorted(mentioned_numbers - source_numbers)

    # Detect source terms that are likely to be method/result claims. This is a warning,
    # not a hard failure, because Chinese paraphrases cannot be matched perfectly.
    source_terms = set(pack.get("terms", []))
    english_terms = set(re.findall(r"[A-Za-z][A-Za-z0-9+\-]{2,}", text.lower()))
    unsupported_terms = sorted(t for t in english_terms if len(t) > 3 and t not in source_terms and t not in {"xhs", "arxiv"})
    warnings: List[str] = []
    if unsupported_numbers:
        warnings.append("numeric_claim_without_abstract_evidence")
    if unsupported_terms:
        warnings.append("english_term_not_seen_in_source")
    if not abstract:
        warnings.append("empty_evidence_pack")
    return {
        "passed": not unsupported_numbers and bool(abstract),
        "warnings": warnings,
        "unsupported_numbers": unsupported_numbers,
        "unsupported_terms": unsupported_terms[:30],
        "evidence_scope": pack.get("source", {}).get("scope", "unknown"),
    }


def validate_file(content_path: Path, pack_path: Path, output_path: Optional[Path] = None) -> Dict:
    result = validate_content(json.loads(content_path.read_text()), json.loads(pack_path.read_text()))
    if output_path:
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--content", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = validate_file(args.content, args.evidence, args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 2)
