import json
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import collect_metrics
import feedback
import publication_store
from generate_content import generate_content
from paper_pipeline import rank_papers


def iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


class FeedbackLedgerTests(unittest.TestCase):
    def row(self, note, observed, likes, impressions=1000, strategy="formula_breakdown"):
        published = observed - timedelta(hours=24)
        return {
            "account_id": "acct",
            "note_id": note,
            "source": "test",
            "counter_scope": "lifetime",
            "published_at": iso(published),
            "observed_at": iso(observed),
            "impressions": impressions,
            "likes": likes,
            "selected_strategy": strategy,
        }

    def test_replay_and_polling_frequency_do_not_inflate_learning(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "metrics.jsonl"
            observed = datetime.now(timezone.utc)
            first = self.row("n1", observed - timedelta(hours=1), 10)
            second = self.row("n1", observed, 30)
            result = feedback.record_batch([first, second], path)
            self.assertEqual(result["inserted"], 2)
            replay = feedback.record_batch([first, second], path)
            self.assertEqual(replay["inserted"], 0)
            stored = feedback._load_rows(path)
            self.assertIsNone(stored[0]["delta"]["likes"])
            self.assertEqual(stored[1]["delta"]["likes"], 20)
            payload = feedback.update_weights(stored, Path(d) / "weights.json")
            self.assertEqual(payload["eligible_notes"], 1)
            # The first 24h observation is the sole training sample.
            self.assertEqual(payload["strategies"]["formula_breakdown"]["observations"], 1)

    def test_missing_exposure_and_counter_reset_are_not_learned(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "metrics.jsonl"
            now = datetime.now(timezone.utc)
            base = self.row("n1", now - timedelta(hours=2), 10, impressions=1000)
            reset = self.row("n1", now, 2, impressions=50)
            missing = self.row("n2", now, 3, impressions=None)
            feedback.record_batch([base, reset], path)
            feedback.record_batch([missing], path)
            payload = feedback.update_weights(feedback._load_rows(path), Path(d) / "weights.json")
            self.assertEqual(payload["eligible_notes"], 0)

    def test_unknown_metrics_are_not_zero_and_views_are_separate(self):
        row = feedback.normalize_row({"account_id": "a", "note_id": "n", "observed_at": iso(datetime.now(timezone.utc)),
                                      "impressions": 100, "views": 20, "likes": 3})
        self.assertEqual(row["views"], 20)
        self.assertIsNone(row["comments"])


class DecisionTests(unittest.TestCase):
    def test_feedback_changes_rank_and_selected_strategy(self):
        papers = [
            {"arxiv_id": "a", "title": "RL objective equation", "summary": "reinforcement learning objective equation loss " * 15, "published": "2026-09-20"},
            {"arxiv_id": "b", "title": "RL foundation model", "summary": "reinforcement learning foundation model benchmark " * 15, "published": "2026-09-20"},
        ]
        ranked_formula = rank_papers(papers, strategy_weights={"formula_breakdown": 0.95, "hot_topic": 0.05})
        ranked_hot = rank_papers(papers, strategy_weights={"formula_breakdown": 0.05, "hot_topic": 0.95})
        score_formula = {p["arxiv_id"]: p["selection_score"]["strategy_fit"] for p in ranked_formula}
        score_hot = {p["arxiv_id"]: p["selection_score"]["strategy_fit"] for p in ranked_hot}
        self.assertGreater(score_formula["a"], score_hot["a"])
        content = generate_content(papers[0], strategy_weights={"formula_breakdown": 0.95})
        self.assertEqual(content["selected_strategy"], "formula_breakdown")
        self.assertEqual(content["strategy_tags"], ["formula_breakdown"])
        self.assertIn("candidate_strategy_tags", content)

    def test_cold_start_uses_neutral_explainer(self):
        paper = {"arxiv_id": "a", "title": "RL objective equation", "summary": "reinforcement learning objective equation"}
        content = generate_content(paper, strategy_weights={})
        self.assertEqual(content["selected_strategy"], "abstract_explainer")
        self.assertEqual(content["strategy_selection_reason"], "cold_start")


class CollectorTests(unittest.TestCase):
    def test_empty_creator_page_fails_without_writing_state(self):
        class EmptyClient:
            def get_notes_statistics(self, **kwargs):
                return {"data": {"items": []}, "more": False}

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(collect_metrics.CollectionError):
                collect_metrics.collect(client=EmptyClient(), creator=True, account_id="acct",
                                        config={"rows_path": "data.items", "has_more_path": "more", "fields": {"note_id": "id"}},
                                        scope="lifetime", snapshots=Path(d) / "m.jsonl", weights=Path(d) / "w.json")
            self.assertFalse((Path(d) / "m.jsonl").exists())

    def test_fake_paginated_creator_writes_snapshot_and_weight(self):
        class FakeClient:
            def get_notes_statistics(self, page, page_size, time, is_recent):
                return {"data": {"items": [{"id": "n1", "stats": {"impressions": 1000, "likes": 40,
                         "published": int((datetime.now(timezone.utc) - timedelta(hours=24)).timestamp()),
                         "selected": "formula_breakdown"}}]}, "more": False}

        with tempfile.TemporaryDirectory() as d:
            config = {"rows_path": "data.items", "has_more_path": "more", "published_time_unit": "seconds",
                      "fields": {"note_id": "id", "impressions": "stats.impressions", "likes": "stats.likes", "published_at": "stats.published", "selected_strategy": "stats.selected"}}
            result = collect_metrics.collect(client=FakeClient(), creator=True, account_id="acct",
                                             config=config, scope="lifetime", snapshots=Path(d) / "m.jsonl", weights=Path(d) / "w.json")
            self.assertEqual(result["inserted"], 1)
            self.assertEqual(result["eligible_notes"], 1)


class PublicationLedgerTests(unittest.TestCase):
    def test_successful_submission_keeps_private_metadata_without_fake_publish_time(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "published.json"
            publication_store.record_publication(
                {"arxiv_id": "1234.1", "original_title": "Paper", "selected_strategy": "abstract_explainer"},
                {"success": True, "note_id": "note-1"}, path=path)
            item = json.loads(path.read_text())["published"][0]
            self.assertEqual(item["xhs_note_id"], "note-1")
            self.assertIsNone(item["published_at"])
            self.assertEqual(item["status"], "submitted")


if __name__ == "__main__":
    unittest.main()
