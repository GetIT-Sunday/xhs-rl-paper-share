#!/usr/bin/env python3
"""Candidate ranking and lightweight evidence packs for Paper2XHS.

The module deliberately uses deterministic, inspectable heuristics.  It does not
claim to replace a paper reader or an LLM reviewer; it makes the selection and
fact boundary explicit so that later generation steps can be audited.
"""

from __future__ import annotations

import json
import math
import os
import re
from datetime import date, datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set


DOMAIN_TERMS = {
    "reinforcement_learning": ("reinforcement learning", "rl", "policy", "reward", "q-learning", "actor-critic", "ppo", "sac", "offline rl"),
    "embodied_ai": ("embodied", "embodiment", "vision-language-action", "vla", "manipulation", "navigation"),
    "robot_learning": ("robot", "robotics", "sim-to-real", "imitation learning", "locomotion", "manipulation"),
    "world_models": ("world model", "model-based", "latent dynamics", "dreamer"),
}

METHOD_TERMS = ("transformer", "diffusion", "foundation model", "large language model", "llm", "multi-agent", "offline", "online", "planning", "generalization")


def strategy_weights_path() -> Path:
    return Path(os.environ.get("PAPER2XHS_DATA_DIR", str(Path(__file__).parent.parent / ".paper2xhs"))) / "strategy_weights.json"

PRIOR_STRATEGY_SCORE = .011 / (.011 + .02)

STRATEGY_CUES = {
    "counterintuitive": ("counterintuitive", "surprising", "unexpected", "paradox", "反直觉"),
    "cross_domain_analogy": ("analogy", "inspired by", "borrow", "cross-domain", "类比"),
    "formula_breakdown": ("equation", "objective", "loss", "formula", "theorem", "公式"),
    "hot_topic": ("foundation model", "llm", "world model", "benchmark", "generalization", "scaling"),
    "abstract_explainer": (),
}


def _text(paper: Dict) -> str:
    return " ".join(str(paper.get(k, "")) for k in ("title", "summary", "categories")).lower()


def infer_strategy_tags(text: str) -> List[str]:
    lowered = text.lower()
    tags = [name for name, cues in STRATEGY_CUES.items() if any(cue in lowered for cue in cues)]
    if "abstract_explainer" not in tags:
        tags.append("abstract_explainer")
    return tags


def load_strategy_policy(path: Optional[Path]) -> Dict:
    """Load a bounded policy snapshot; malformed state means cold start."""
    if not path or not path.exists():
        return {"weights": {}, "version": None, "updated_at": None, "eligible_notes": 0}
    try:
        payload = json.loads(path.read_text())
        if payload.get("schema_version") != 2 or not isinstance(payload.get("strategies"), dict):
            return {"weights": {}, "version": None, "updated_at": None, "eligible_notes": 0}
        account = os.environ.get("XHS_ACCOUNT_ID")
        if account and payload.get("account_id") != account:
            raise ValueError("policy account mismatch")
        updated = datetime.fromisoformat(payload["updated_at"].replace("Z", "+00:00"))
        if updated.tzinfo is None or not timedelta(0) <= datetime.now(timezone.utc) - updated <= timedelta(days=14):
            raise ValueError("stale policy")
        weights = {}
        for tag, item in payload["strategies"].items():
            value = float(item.get("posterior_mean"))
            if math.isfinite(value) and 0.0 <= value <= 1.0:
                weights[str(tag)] = value
        return {"weights": weights, "version": payload.get("version"),
                "updated_at": payload.get("updated_at"),
                "eligible_notes": int(payload.get("eligible_notes", 0) or 0)}
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return {"weights": {}, "version": None, "updated_at": None, "eligible_notes": 0}


def load_strategy_weights(path: Optional[Path]) -> Dict[str, float]:
    return load_strategy_policy(path)["weights"]


def _published_ids(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError):
        return set()
    return {str(item.get("arxiv_id")) for item in payload.get("published", []) if item.get("arxiv_id")}


def _recency_score(published: str, today: Optional[date] = None) -> float:
    try:
        age = (today or date.today()) - datetime.strptime(published[:10], "%Y-%m-%d").date()
        return max(0.0, min(1.0, math.exp(-max(age.days, 0) / 45.0)))
    except (TypeError, ValueError):
        return 0.0


def score_paper(paper: Dict, published_ids: Iterable[str] = (), strategy_weights: Optional[Dict[str, float]] = None) -> Dict:
    """Return transparent component scores in [0, 1] plus a weighted total."""
    text = _text(paper)
    domain_hits = {name: sum(1 for term in terms if term in text) for name, terms in DOMAIN_TERMS.items()}
    domain_score = min(1.0, sum(domain_hits.values()) / 8.0)
    method_score = min(1.0, sum(1 for term in METHOD_TERMS if term in text) / 5.0)
    # Longer abstracts tend to expose enough method/result detail for a safe note.
    evidence_score = min(1.0, len(str(paper.get("summary", ""))) / 900.0)
    novelty_score = 0.0 if str(paper.get("arxiv_id")) in set(published_ids) else 1.0
    recency_score = _recency_score(str(paper.get("published", "")))
    # A modest, explainable proxy for visual/communication potential.
    visual_score = min(1.0, (len(str(paper.get("title", ""))) / 90.0) * 0.5 + method_score * 0.5)
    tags = infer_strategy_tags(text)
    strategy_weights = strategy_weights or {}
    strategy_bonus = sum(strategy_weights.get(tag, PRIOR_STRATEGY_SCORE) for tag in tags) / max(len(tags), 1)
    strategy_bonus = max(0.0, min(1.0, strategy_bonus))
    total = (
        0.30 * domain_score
        + 0.15 * recency_score
        + 0.15 * novelty_score
        + 0.20 * evidence_score
        + 0.10 * method_score
        + 0.05 * visual_score
        + 0.05 * strategy_bonus
    )
    return {
        "total": round(total, 4),
        "domain_relevance": round(domain_score, 4),
        "recency": round(recency_score, 4),
        "novelty": round(novelty_score, 4),
        "evidence": round(evidence_score, 4),
        "method_richness": round(method_score, 4),
        "visual_proxy": round(visual_score, 4),
        "strategy_fit": round(strategy_bonus, 4),
        "strategy_tags": tags,
        "domain_hits": domain_hits,
    }


def rank_papers(papers: List[Dict], published_ids: Iterable[str] = (), strategy_weights: Optional[Dict[str, float]] = None) -> List[Dict]:
    published = set(published_ids)
    ranked = []
    for paper in papers:
        item = dict(paper)
        item["selection_score"] = score_paper(item, published, strategy_weights)
        ranked.append(item)
    return sorted(ranked, key=lambda item: item["selection_score"]["total"], reverse=True)


def _sentences(summary: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?。！？])\s+", summary.replace("\n", " ")) if s.strip()]


def build_evidence_pack(paper: Dict, output_path: Path) -> Dict:
    """Create a compact evidence pack from metadata/abstract available locally."""
    summary = str(paper.get("summary", paper.get("abstract", ""))).strip()
    sentences = _sentences(summary)
    pack = {
        "schema_version": "1.0",
        "arxiv_id": paper.get("arxiv_id", ""),
        "title": paper.get("title", paper.get("original_title", "")),
        "source": {
            "arxiv_url": paper.get("arxiv_url") or f"https://arxiv.org/abs/{paper.get('arxiv_id', '')}",
            "pdf_url": paper.get("pdf_url") or f"https://arxiv.org/pdf/{paper.get('arxiv_id', '')}",
            "retrieved_at": datetime.now().isoformat(),
            "scope": "metadata_and_abstract",
        },
        "claims": [
            {"id": f"abstract_{idx + 1}", "claim": sentence, "evidence": sentence, "source": "abstract"}
            for idx, sentence in enumerate(sentences)
        ],
        "numbers": sorted(set(re.findall(r"(?<![A-Za-z])\d+(?:\.\d+)?%?", summary))),
        "terms": sorted(set(re.findall(r"[A-Za-z][A-Za-z0-9+\-]{2,}", f"{paper.get('title', '')} {summary}".lower()))),
        "limitations": ["This pack only covers metadata and abstract evidence; full-text claims require a paper reader."],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(pack, ensure_ascii=False, indent=2))
    return pack


def load_evidence_pack(path: Path) -> Dict:
    return json.loads(path.read_text())
