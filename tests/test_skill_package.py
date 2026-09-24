"""Test the distributable as a user would: extract elsewhere and invoke its CLI."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from package_skill import build, FILES


@unittest.skipIf(sys.version_info < (3, 10), 'Skill runtime requires Python 3.10+')
class SkillPackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='paper2xhs skill ')
        self.root = Path(self.temp.name)
        self.archive = build(self.root / 'paper2xhs.zip')
        with zipfile.ZipFile(self.archive) as z:
            z.extractall(self.root / 'installed')
        self.skill = self.root / 'installed' / 'paper2xhs'
        self.home = self.root / 'private account'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(('XHS_', 'PAPER2XHS_'))}
        self.env.update(PAPER2XHS_HOME=str(self.home), PYTHONDONTWRITEBYTECODE='1')

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, code=0):
        result = subprocess.run([sys.executable, str(self.skill / 'scripts/paper2xhs.py'), *args],
                                cwd=self.root, env=self.env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        return result

    def test_package_is_allowlisted_and_doctor_never_discloses_cookie(self):
        with zipfile.ZipFile(self.archive) as z:
            self.assertEqual(set(z.namelist()), {'paper2xhs/' + p for p in FILES})
            self.assertFalse(any('published_papers' in p or 'fetched_papers' in p or 'content_' in p for p in z.namelist()))
        self.env['XHS_COOKIE'] = 'SECRET_SENTINEL_COOKIE'
        result = self.run_cli('doctor')
        self.assertNotIn('SECRET_SENTINEL_COOKIE', result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)['cookie_configured'])
        self.assertFalse(self.home.exists())

    def test_clean_install_generates_collects_and_preserves_private_state(self):
        original = {str(p.relative_to(self.skill)): p.read_bytes() for p in self.skill.rglob('*') if p.is_file()}
        self.run_cli('setup', '--skip-deps')
        paper = self.root / 'synthetic paper.json'
        paper.write_text(json.dumps({'arxiv_id': '0000.00001', 'title': 'Synthetic RL objective',
                                     'summary': 'Reinforcement learning objective for robot policies.'}))
        self.run_cli('run', 'generate', '--', '--paper-json', str(paper))
        draft = self.home / 'app/references/content_0000_00001.json'
        self.assertEqual(json.loads(draft.read_text())['selected_strategy'], 'abstract_explainer')
        # Synthetic observations exercise the entire private collection/policy/report path.
        export = self.root / 'synthetic metrics.json'
        export.write_text(json.dumps([{'note_id': 'synthetic-note', 'account_id': 'synthetic-account',
            'published_at': '2026-09-01T00:00:00+00:00', 'observed_at': '2026-09-02T00:00:00+00:00',
            'impressions': 1000, 'likes': 50, 'selected_strategy': 'formula_breakdown'}]))
        self.run_cli('run', 'collect', '--', '--source', str(export), '--account-id', 'synthetic-account', '--scope', 'lifetime')
        weights = json.loads((self.home / 'data/strategy_weights.json').read_text())
        self.assertEqual(weights['eligible_notes'], 1)
        replay = self.run_cli('run', 'collect', '--', '--source', str(export), '--account-id', 'synthetic-account', '--scope', 'lifetime')
        self.assertEqual(json.loads(replay.stdout)['inserted'], 0)
        self.run_cli('run', 'feedback', '--', 'report')
        self.assertTrue((self.home / 'data/feedback_report.md').exists())
        self.run_cli('prepare')
        decision = json.loads((self.home / 'data/last_decision.json').read_text())
        self.assertEqual(decision['selected_strategy'], 'formula_breakdown')
        ledger = (self.home / 'data/metrics_snapshots.jsonl').read_bytes()
        self.run_cli('setup', '--skip-deps')
        self.assertEqual(ledger, (self.home / 'data/metrics_snapshots.jsonl').read_bytes())
        after = {str(p.relative_to(self.skill)): p.read_bytes() for p in self.skill.rglob('*') if p.is_file()}
        self.assertEqual(original, after, 'Installed Skill must stay immutable')

    def test_rejects_private_runtime_inside_installed_skill(self):
        self.env['PAPER2XHS_HOME'] = str(self.skill / 'runtime')
        self.run_cli('setup', '--skip-deps', code=2)
        self.assertFalse((self.skill / 'runtime').exists())

    def test_empty_prepare_does_not_publish(self):
        self.run_cli('setup', '--skip-deps')
        self.run_cli('prepare', code=2)
        self.assertFalse((self.home / 'data/published_papers.json').exists())


if __name__ == '__main__':
    unittest.main()
