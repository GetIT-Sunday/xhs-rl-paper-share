#!/usr/bin/env python3
"""Read-only collection: creator API (xhs), mapped JSON endpoint, or CSV/JSON.

Live schema is configurable and must be checked against the logged-in account.
No publishing or credential extraction. Empty/error/partial pages never replace
an existing policy. Snapshot data and derived weights stay in the local data dir.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from feedback import (DATA_DIR, DEFAULT_METRICS, DEFAULT_WEIGHTS, _load_rows,
                      atomic_text, normalize_row, record_batch, update_weights, utcnow)
from publication_store import LEGACY_PATH, load_published


class CollectionError(ValueError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CollectionError('采集接口发生重定向；请检查登录状态和接口配置')


def read_source(source, cookie=None):
    parsed = urllib.parse.urlsplit(source)
    if not parsed.scheme:
        path = Path(source)
        if path.suffix.lower() == '.csv':
            with path.open(newline='', encoding='utf-8-sig') as handle:
                return list(csv.DictReader(handle))
        return json.loads(path.read_text(encoding='utf-8'))
    # Cookies must never go to a third-party endpoint or follow a redirect.
    if parsed.scheme != 'https' or parsed.hostname != 'creator.xiaohongshu.com' or parsed.username or parsed.password:
        raise CollectionError('远程采集只允许 https://creator.xiaohongshu.com；其他源请使用本地导出文件')
    request = urllib.request.Request(source, headers={'User-Agent': 'Paper2XHS/2',
                                                     'Referer': 'https://creator.xiaohongshu.com/'})
    if cookie:
        request.add_header('Cookie', cookie)
    opener = urllib.request.build_opener(NoRedirect())
    for attempt in range(3):
        try:
            with opener.open(request, timeout=20) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403, 461, 471):
                raise CollectionError('登录失效或需要验证，请在创作者中心处理后再采集') from None
            if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise CollectionError('只读采集请求失败，HTTP ' + str(exc.code)) from None
        except urllib.error.URLError:
            if attempt == 2:
                raise CollectionError('无法连接创作者中心') from None
        time.sleep(2 ** attempt)


def dotted(data, path):
    for key in path.split('.') if path else []:
        if not isinstance(data, dict) or key not in data:
            raise CollectionError('响应缺少已配置的字段路径: ' + path)
        data = data[key]
    return data


def find_rows(payload, rows_path=None):
    if isinstance(payload, dict) and (payload.get('success') is False or payload.get('isError') is True):
        raise CollectionError('平台返回业务错误；请检查登录状态，未写入数据')
    if rows_path is not None:
        payload = dotted(payload, rows_path)
    if isinstance(payload, dict) and 'notes' in payload:
        payload = payload['notes']
    if not isinstance(payload, list) or any(not isinstance(r, dict) for r in payload):
        raise CollectionError('需要笔记数组；嵌套响应请配置 rows_path，不能自动猜字段')
    return payload


def map_row(raw, config):
    if not config.get('fields'):
        return dict(raw)
    result = {}
    for canonical, path in config['fields'].items():
        try:
            result[canonical] = dotted(raw, path)
        except CollectionError:
            if canonical in ('note_id',):
                raise
            result[canonical] = None
    # Explicit unit only. Never guess seconds vs milliseconds or local timezone.
    if result.get('published_at') is not None and config.get('published_time_unit') in ('seconds', 'milliseconds'):
        scale = 1000 if config['published_time_unit'] == 'milliseconds' else 1
        result['published_at'] = datetime.fromtimestamp(float(result['published_at']) / scale, timezone.utc).isoformat()
    return result


def creator_pages(client, config, max_pages=20, page_size=48):
    """The read-only method is present in PyPI xhs 0.2.13; field schema is supplied separately."""
    if not config.get('fields') or 'rows_path' not in config:
        raise CollectionError('实号采集需要已核对的 rows_path 和 fields 配置')
    seen = set()
    all_rows = []
    for page in range(1, max_pages + 1):
        try:
            # Older xhs versions print complete API responses; suppress account data in logs.
            with open(os.devnull, 'w') as sink, contextlib.redirect_stdout(sink):
                payload = client.get_notes_statistics(page=page, page_size=page_size,
                            time=config.get('days', 30), is_recent=config.get('is_recent', True))
        except Exception:
            raise CollectionError('创作者指标接口读取失败：可能登录失效、签名变化或需要验证') from None
        batch = find_rows(payload, config['rows_path'])
        digest = hashlib.sha256(json.dumps(batch, sort_keys=True).encode()).hexdigest()
        if batch and digest in seen:
            raise CollectionError('分页重复，停止并保留旧数据')
        seen.add(digest)
        all_rows.extend(batch)
        more_path = config.get('has_more_path')
        if more_path:
            more = dotted(payload, more_path)
            if not isinstance(more, bool):
                raise CollectionError('has_more 必须是布尔值')
            if not more:
                return all_rows
        elif len(batch) < page_size:
            return all_rows
        time.sleep(.3)
    raise CollectionError('达到分页上限，未保存不完整采集；请提高 max_pages')


def published_metadata(path, account_id):
    if path and Path(path).exists():
        payload = load_published(Path(path), legacy=LEGACY_PATH)
    else:
        payload = load_published()
    return {str(r['xhs_note_id']): r for r in payload.get('published', [])
            if r.get('xhs_note_id') and (not r.get('account_id') or r.get('account_id') == account_id)}


def collect(source=None, snapshots=DEFAULT_METRICS, weights=DEFAULT_WEIGHTS, cookie=None,
            account_id=None, scope='unknown', dry_run=False, config=None, creator=False,
            client=None, published=None, max_pages=20):
    config = config or {}
    if not account_id:
        raise CollectionError('需要 account_id，用于隔离账号数据')
    if creator:
        if client is None:
            if not cookie:
                raise CollectionError('未配置 XHS_COOKIE；请先在创作者中心登录并在本地配置凭证')
            # Reuse existing signed client; calling its constructor does not publish.
            from publish_to_xhs import create_xhs_client
            client = create_xhs_client(cookie)
        raw_rows = creator_pages(client, config, max_pages)
        observed = utcnow()
    else:
        if not source:
            raise CollectionError('需要 --source 或 --creator')
        payload = read_source(source, cookie)
        raw_rows = find_rows(payload, config.get('rows_path'))
        if urllib.parse.urlsplit(source).scheme:
            observed = utcnow()
        else:
            # Re-importing an unchanged export must not pretend it is a new observation.
            observed = datetime.fromtimestamp(Path(source).stat().st_mtime, timezone.utc).isoformat()
    if not raw_rows:
        raise CollectionError('没有读到笔记，不更新已有权重')
    metadata = published_metadata(published, account_id)
    rows = []
    seen = set()
    for raw in raw_rows:
        row = map_row(raw, config)
        row.setdefault('account_id', account_id)
        if row['account_id'] != account_id:
            raise CollectionError('响应账号与配置账号不一致')
        row.setdefault('observed_at', observed)
        row.setdefault('source', config.get('source_id', 'creator_api' if creator else 'creator_export'))
        row.setdefault('counter_scope', scope)
        row = normalize_row(row)
        identity = (row['note_id'], row['observed_at'])
        if identity in seen:
            raise CollectionError('同一批次有重复笔记；请检查分页或响应映射')
        seen.add(identity)
        meta = metadata.get(row['note_id'], {})
        # Join via account + platform note ID, never title similarity or hashtags.
        if not row.get('selected_strategy') and meta.get('selected_strategy'):
            row['selected_strategy'] = meta['selected_strategy']
            row['strategy_tags'] = [meta['selected_strategy']]
            row['policy_version'] = meta.get('policy_version')
        if not row.get('published_at') and meta.get('published_at'):
            # Legacy records may contain a naive local timestamp. Keep the
            # strategy join, but never guess its timezone for age learning.
            value = str(meta['published_at'])
            if 'T' in value and ('+' in value[10:] or value.endswith('Z')):
                row['published_at'] = value
        rows.append(row)
    result = record_batch(rows, snapshots, dry_run=dry_run)
    if not dry_run:
        result['eligible_notes'] = update_weights(_load_rows(snapshots), weights,
            config.get('horizon_hours', 24), config.get('tolerance_hours', 6))['eligible_notes']
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', '--endpoint', dest='source', default=os.environ.get('XHS_METRICS_ENDPOINT'))
    parser.add_argument('--creator', action='store_true', help='Use signed read-only xhs creator statistics API')
    parser.add_argument('--config', type=Path, default=Path(os.environ['XHS_METRICS_CONFIG']) if os.environ.get('XHS_METRICS_CONFIG') else None)
    parser.add_argument('--account-id', default=os.environ.get('XHS_ACCOUNT_ID'))
    parser.add_argument('--scope', default='unknown', help='Use lifetime only after verifying cumulative counter semantics')
    parser.add_argument('--snapshots', type=Path, default=DEFAULT_METRICS)
    parser.add_argument('--weights', type=Path, default=DEFAULT_WEIGHTS)
    parser.add_argument('--published', type=Path, default=DATA_DIR / 'published_papers.json')
    parser.add_argument('--max-pages', type=int, default=20)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    try:
        config = json.loads(args.config.read_text()) if args.config else {}
        result = collect(args.source, args.snapshots, args.weights, os.environ.get('XHS_COOKIE'),
                         args.account_id, config.get('counter_scope', args.scope), args.dry_run,
                         config, args.creator, published=args.published, max_pages=args.max_pages)
        if not args.dry_run:
            atomic_text(DATA_DIR / 'collection_status.json', json.dumps({'at': utcnow(), 'ok': True, **result}))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, OSError, ImportError) as exc:
        # Error text is controlled; never print URLs containing tokens or raw responses.
        reason = str(exc) if isinstance(exc, ValueError) and not isinstance(exc, json.JSONDecodeError) else type(exc).__name__
        if not args.dry_run:
            atomic_text(DATA_DIR / 'collection_status.json', json.dumps({'at': utcnow(), 'ok': False, 'error': reason}))
        parser.exit(2, 'Collection failed: ' + reason + '\n')


if __name__ == '__main__':
    main()
