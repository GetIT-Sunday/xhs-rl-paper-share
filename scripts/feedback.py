#!/usr/bin/env python3
"""Local cumulative snapshot ledger and exposure-normalized feedback policy.

No account data is needed in Git. Snapshots are the source of truth; signed
counter deltas are diagnostic only. Training uses ONE observation per note at
24--30 hours by default, never one observation per polling interval.
"""
from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import json
import math
import os
import re
import tempfile
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(os.environ.get('PAPER2XHS_DATA_DIR', str(Path(__file__).resolve().parent.parent / '.paper2xhs')))
DEFAULT_METRICS = DATA_DIR / 'metrics_snapshots.jsonl'
DEFAULT_WEIGHTS = DATA_DIR / 'strategy_weights.json'
DEFAULT_REPORT = DATA_DIR / 'feedback_report.md'
COUNTERS = ('impressions', 'views', 'likes', 'saves', 'comments', 'shares', 'new_followers')
REWARDS = {'likes': 1.0, 'saves': 2.0, 'comments': 2.0, 'shares': 2.0, 'new_followers': 4.0}
STRATEGY_ALIASES = {'反直觉': 'counterintuitive', '反直觉结论': 'counterintuitive',
                    '跨领域类比': 'cross_domain_analogy', '公式拆解': 'formula_breakdown',
                    '公式化拆解': 'formula_breakdown', '热点关联': 'hot_topic'}
HEADER_ALIASES = {
    'note_id': ('note_id', 'noteid', '笔记id', '笔记 id'),
    'account_id': ('account_id', 'accountid', '账号id'),
    'published_at': ('published_at', 'publishtime', 'publish_time', '发布时间'),
    'observed_at': ('observed_at', 'snapshot_at', '采集时间', '统计时间'),
    'source': ('source', '数据来源'),
    'counter_scope': ('counter_scope', '统计口径'),
    'title': ('title', '标题', '笔记标题'),
    'impressions': ('impressions', 'impressioncount', 'exposurecount', '曝光量', '曝光'),
    'views': ('views', 'viewcount', 'readcount', '阅读量', '观看量', '浏览量'),
    'likes': ('likes', 'likecount', '点赞数', '点赞'),
    'saves': ('saves', 'savecount', 'collectcount', 'favoritecount', '收藏数', '收藏'),
    'comments': ('comments', 'commentcount', '评论数', '评论'),
    'shares': ('shares', 'sharecount', '分享数', '分享'),
    # Account net followers are deliberately NOT an alias for note attribution.
    'new_followers': ('new_followers', 'fansincrement', 'followerincrement', '笔记涨粉', '笔记涨粉数'),
    'strategy_tags': ('strategy_tags', '策略标签'),
    'selected_strategy': ('selected_strategy', '选用策略'),
    'policy_version': ('policy_version',),
}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
    if dt.tzinfo is None:
        raise ValueError('时间必须包含时区，例如 2026-09-22T10:00:00+08:00')
    return dt.astimezone(timezone.utc)


def _number(value):
    if value is None or str(value).strip() in ('', '--', '-', '—', 'N/A'):
        return None
    text = str(value).strip().replace(',', '')
    if text.endswith('+') or text.endswith('%'):
        raise ValueError('近似下界/百分比不能当作累计计数')
    factor = 10000 if text.endswith('万') else 1000 if text.endswith('千') else 1
    result = float(text[:-1] if factor != 1 else text) * factor
    if not math.isfinite(result) or result < 0 or not result.is_integer():
        raise ValueError('计数必须是有限的非负整数')
    return int(result)


def _tags(value):
    items = value if isinstance(value, list) else re.split(r'[,，;；|]', str(value or ''))
    return sorted(set(STRATEGY_ALIASES.get(str(t).strip().lstrip('#'), str(t).strip().lstrip('#'))
                      for t in items if str(t).strip()))


def normalize_row(raw):
    if not isinstance(raw, dict):
        raise ValueError('每条观测必须是对象')
    lowered = {str(k).strip().lower(): v for k, v in raw.items()}
    row = {}
    for key, aliases in HEADER_ALIASES.items():
        for alias in aliases:
            if alias.lower() in lowered:
                row[key] = lowered[alias.lower()]
                break
    for key in COUNTERS:
        row[key] = _number(row.get(key))
    row['strategy_tags'] = _tags(row.get('strategy_tags'))
    if row.get('selected_strategy'):
        row['selected_strategy'] = _tags([row['selected_strategy']])[0]
    for key in ('account_id', 'note_id'):
        row[key] = str(row.get(key) or '').strip()
        if not row[key]:
            raise ValueError('缺少 ' + key)
    row['source'] = str(row.get('source') or 'manual')
    row['counter_scope'] = str(row.get('counter_scope') or 'unknown')
    row['observed_at'] = timestamp(row.get('observed_at') or utcnow()).isoformat()
    if row.get('published_at'):
        row['published_at'] = timestamp(row['published_at']).isoformat()
        if timestamp(row['published_at']) > timestamp(row['observed_at']):
            raise ValueError('发布时间晚于观测时间')
    if not any(row[k] is not None for k in COUNTERS):
        raise ValueError('未识别到指标字段；请检查字段映射')
    return row


def stream_key(row):
    return tuple(row[k] for k in ('account_id', 'note_id', 'source', 'counter_scope'))


def normalized_metrics(row):
    n = row.get('impressions')
    rates = {k + '_per_1k': (1000 * row[k] / n if n and row.get(k) is not None else None)
             for k in REWARDS}
    age = None
    if row.get('published_at'):
        age = (timestamp(row['observed_at']) - timestamp(row['published_at'])).total_seconds() / 3600
    return {**rates, 'age_hours': age, 'has_exposure': bool(n)}


def _load_rows(path):
    if not Path(path).exists():
        return []
    # Fail on corruption instead of silently dropping evidence.
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines() if line.strip()]


@contextmanager
def file_lock(path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('a') as handle:
        os.chmod(path, 0o600)
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def atomic_text(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def record_batch(incoming, metrics_path=DEFAULT_METRICS, dry_run=False):
    rows = [normalize_row(row) for row in incoming]  # Validate the entire batch before writing.
    metrics_path = Path(metrics_path)
    def merge(existing):
        by_id = {}
        for row in existing:
            if row.get('schema_version') != 2:
                raise ValueError('旧反馈文件不能自动当累计快照迁移；请重新导入原始报表')
            by_id[(stream_key(row), row['observed_at'])] = row
        added = 0
        for row in rows:
            identity = (stream_key(row), row['observed_at'])
            if identity in by_id:
                previous = normalize_row(by_id[identity])
                if previous != row:
                    raise ValueError('同一笔记同一时间出现冲突观测')
                continue
            by_id[identity] = {**row, 'schema_version': 2}
            added += 1
        ordered = sorted(by_id.values(), key=lambda r: (stream_key(r), r['observed_at']))
        prev = {}
        # Recompute even for out-of-order imports. Deltas are signed corrections,
        # missing counters never become zero, and first observations are baselines.
        for row in ordered:
            key = stream_key(row)
            before = prev.get(key)
            row['delta'] = {k: row[k] - before[k]
                            if before and row.get(k) is not None and before.get(k) is not None else None
                            for k in COUNTERS}
            row['counter_decreases'] = [k for k, v in row['delta'].items() if v is not None and v < 0]
            row['normalized'] = normalized_metrics(row)
            prev[key] = row
        return ordered, added
    if dry_run:
        ordered, added = merge(_load_rows(metrics_path))
    else:
        with file_lock(metrics_path.with_suffix('.lock')):
            ordered, added = merge(_load_rows(metrics_path))
            if added:
                atomic_text(metrics_path, ''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in ordered))
    return {'captured': len(rows), 'inserted': added, 'duplicates': len(rows) - added,
            'snapshot_count': len(ordered), 'dry_run': dry_run}


def record(row, metrics_path=DEFAULT_METRICS):
    return record_batch([row], metrics_path)


def read_export(path):
    path = Path(path)
    if path.suffix.lower() == '.csv':
        with path.open(newline='', encoding='utf-8-sig') as handle:
            return list(csv.DictReader(handle))
    payload = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and isinstance(payload.get('notes'), list):
        return payload['notes']
    if isinstance(payload, dict) and ('note_id' in payload or '笔记ID' in payload):
        return [payload]
    raise ValueError('需要 JSON 数组、notes 数组或 CSV 表格；不自动猜测嵌套字段')


def import_file(path, metrics_path=DEFAULT_METRICS, account_id=None, scope='unknown'):
    observed = datetime.fromtimestamp(Path(path).stat().st_mtime, timezone.utc).isoformat()
    rows = read_export(path)
    for row in rows:
        row.setdefault('observed_at', observed)
        row.setdefault('account_id', account_id)
        row.setdefault('counter_scope', scope)
        row.setdefault('source', 'creator_export')
    return record_batch(rows, metrics_path)


def learning_rows(rows, horizon=24, tolerance=6):
    groups = defaultdict(list)
    for raw in rows:
        if raw.get('schema_version') != 2:
            raise ValueError('学习输入必须是 schema_version=2 累计快照')
        row = normalize_row(raw)
        row['counter_decreases'] = raw.get('counter_decreases', [])
        age = normalized_metrics(row)['age_hours']
        if row['counter_scope'] != 'lifetime' or age is None or not horizon <= age <= horizon + tolerance:
            continue
        # Exact duplicates/repeated polls cannot create extra samples.
        groups[(row['account_id'], row['note_id'])].append(row)
    chosen = []
    for candidates in groups.values():
        # Multiple sources/strategies for one note are ambiguous: do not guess attribution.
        if len({(r['source'], r.get('selected_strategy')) for r in candidates}) != 1:
            continue
        if any(r.get('counter_decreases') for r in candidates):
            continue
        valid = [r for r in candidates
                 if not r.get('counter_decreases')
                 and r.get('impressions') is not None
                 and r.get('impressions', 0) > 0]
        if valid:
            chosen.append(min(valid, key=lambda r: r['observed_at']))
    return chosen


def update_weights(rows, output_path=DEFAULT_WEIGHTS, horizon=24, tolerance=6):
    if horizon <= 0 or tolerance < 0:
        raise ValueError('invalid observation horizon')
    rows = list(rows)
    chosen = learning_rows(rows, horizon, tolerance)
    accounts = {r['account_id'] for r in rows}
    if len(accounts) > 1:
        raise ValueError('每个反馈目录仅支持一个账号，避免混用策略权重')
    stats = {}
    used = []
    for row in chosen:
        tag = row.get('selected_strategy')
        # Legacy explicit single-label imports may be used; candidate tags are never all credited.
        if not tag and len(row['strategy_tags']) == 1:
            tag = row['strategy_tags'][0]
        n = row.get('impressions')
        if not tag or not n:
            continue
        observed = {k: row[k] for k in REWARDS if row[k] is not None}
        if not observed:
            continue
        used.append(row)
        stats.setdefault(tag, {'observations': 0, 'metrics': {}})['observations'] += 1
        # Gamma-Poisson smooths event counts per exposure (comments need not be Bernoulli).
        # Cap each note's exposure contribution at 10k, a documented robust pseudo-likelihood.
        factor = min(n, 10000) / n
        for metric, count in observed.items():
            state = stats[tag]['metrics'].setdefault(metric, {'shape': 1.0, 'rate': 1000.0, 'notes': 0})
            state['shape'] += count * factor
            state['rate'] += n * factor
            state['notes'] += 1
    for item in stats.values():
        weighted = 0.0
        for metric, state in item['metrics'].items():
            state['posterior_mean'] = state['shape'] / state['rate']
            state['posterior_std'] = math.sqrt(state['shape']) / state['rate']
            weighted += REWARDS[metric] * state['posterior_mean']
        # Comparable bounded score; unavailable metrics retain the prior rate, not a fake zero.
        weighted += sum(w * .001 for k, w in REWARDS.items() if k not in item['metrics'])
        item['utility_rate'] = weighted
        item['posterior_mean'] = weighted / (weighted + .02)
    fingerprint = hashlib.sha256(json.dumps({'rows': used, 'horizon': horizon, 'tolerance': tolerance, 'method': 'capped_gamma_poisson_v2'}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
    payload = {'schema_version': 2, 'updated_at': utcnow(), 'version': fingerprint,
               'account_id': next(iter(accounts), None), 'method': 'capped_gamma_poisson',
               'horizon_hours': horizon, 'tolerance_hours': tolerance, 'eligible_notes': len(used),
               'strategies': stats,
               'limitations': 'Observational association, not causal lift; publication-hour confounding remains.'}
    atomic_text(output_path, json.dumps(payload, ensure_ascii=False, indent=2) + '\n')
    return payload


def latest_rows(rows):
    latest = {}
    for row in rows:
        key = (row['account_id'], row['note_id'])
        if key not in latest or row['observed_at'] > latest[key]['observed_at']:
            latest[key] = row
    return list(latest.values())


def build_report(rows, weights, output_path=DEFAULT_REPORT, account=None):
    latest = latest_rows(rows)
    totals = {k: sum(r[k] for r in latest if r.get(k) is not None) for k in COUNTERS}
    coverage = {k: sum(r.get(k) is not None for r in latest) for k in COUNTERS}
    totals = {k: v if coverage[k] else None for k, v in totals.items()}
    result = {'note_count': len(latest), 'snapshot_count': len(rows), 'totals': totals,
              'coverage': coverage, 'eligible_notes': weights.get('eligible_notes', 0),
              'account_summary': account or {}}
    lines = ['# Paper2XHS 运营反馈', '', '各指标为每篇笔记最新累计值之和；不是采集次数之和。',
             f"笔记：{len(latest)}；快照：{len(rows)}；参与学习：{result['eligible_notes']}", '',
             '| 指标 | 已知合计 | 有值笔记数 |', '|---|---:|---:|']
    lines += [f"| {k} | {v if v is not None else '未知'} | {coverage[k]} |" for k, v in totals.items()]
    lines += ['', '账号净增粉丝不自动归因到单篇笔记；不同字段的缺失覆盖率不可混算转化率。',
              '实际数据留在本地。权重只反映观察相关性，尚不能证明策略带来因果提升。']
    atomic_text(output_path, '\n'.join(lines) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    for command in ('record', 'import', 'update', 'report'):
        p = sub.add_parser(command)
        p.add_argument('--metrics', type=Path, default=DEFAULT_METRICS)
        if command == 'record':
            p.add_argument('--json', required=True)
        if command == 'import':
            p.add_argument('--file', type=Path, required=True)
            p.add_argument('--account-id')
            p.add_argument('--scope', default='unknown')
        if command in ('update', 'report'):
            p.add_argument('--weights', type=Path, default=DEFAULT_WEIGHTS)
            p.add_argument('--horizon-hours', type=float, default=24)
            p.add_argument('--tolerance-hours', type=float, default=6)
        if command == 'report':
            p.add_argument('--output', type=Path, default=DEFAULT_REPORT)
            p.add_argument('--account-json', type=Path)
    args = parser.parse_args()
    try:
        if args.command == 'record':
            raw = json.loads(args.json) if args.json.lstrip().startswith('{') else json.loads(Path(args.json).read_text())
            result = record(raw, args.metrics)
        elif args.command == 'import':
            result = import_file(args.file, args.metrics, args.account_id, args.scope)
        else:
            rows = _load_rows(args.metrics)
            result = update_weights(rows, args.weights, args.horizon_hours, args.tolerance_hours)
            if args.command == 'report':
                account = json.loads(args.account_json.read_text()) if args.account_json else None
                result = build_report(rows, result, args.output, account)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(2, f'Feedback error: {exc}\n')


if __name__ == '__main__':
    main()
