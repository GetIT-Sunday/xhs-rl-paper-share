"""Private publication ledger, with read-only compatibility for legacy records."""
import json
import os
import re
from pathlib import Path
from feedback import DATA_DIR, atomic_text, file_lock, utcnow

PUBLISHED_PATH = DATA_DIR / 'published_papers.json'
LEGACY_PATH = Path(__file__).resolve().parent.parent / 'references' / 'published_papers.json'


def paper_id(value):
    return re.sub(r'v\d+$', '', str(value or ''))


def load_published(path=PUBLISHED_PATH, legacy=LEGACY_PATH):
    records = []
    for location in (legacy, path):
        if location and Path(location).exists():
            records.extend(json.loads(Path(location).read_text()).get('published', []))
    return {'published': records}


def record_publication(content, result, schedule=None, path=PUBLISHED_PATH):
    if not result.get('success'):
        return
    # Submission time is not a verified publication time; collection supplies
    # the latter. Scheduled submissions must never start their age clock now.
    row = {'arxiv_id': content.get('arxiv_id'), 'title': content.get('original_title'),
           'submitted_at': utcnow(), 'published_at': None, 'scheduled_at': schedule,
           'status': 'scheduled' if schedule else 'submitted',
           'account_id': os.environ.get('XHS_ACCOUNT_ID'),
           'xhs_note_id': result.get('note_id') or '', 'xhs_link': result.get('share_link') or '',
           'selected_strategy': content.get('selected_strategy'),
           'strategy_tags': content.get('strategy_tags', []),
           'policy_version': content.get('policy_version'),
           'evidence_pack': content.get('evidence_pack')}
    with file_lock(Path(path).with_suffix('.lock')):
        payload = load_published(path, legacy=None)
        payload['published'].append(row)
        atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
