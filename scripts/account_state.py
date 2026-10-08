"""Private configuration and account binding shared by wizard and publishing."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
import time


def private_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, temporary = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(data, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_json(path):
    try:
        value = json.loads(Path(path).read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def home_path():
    return Path(os.environ.get('PAPER2XHS_HOME', '~/.local/share/paper2xhs')).expanduser().resolve()


def current_cookie(cache):
    value = os.environ.get('XHS_COOKIE') or read_json(cache).get('cookie', '')
    return value if isinstance(value, str) else ''


def fingerprint(cookie):
    # SDKs reorder fields and alter whitespace when reading the cookie jar.
    fields = dict(part.strip().split('=', 1) for part in cookie.split(';') if '=' in part)
    canonical = json.dumps(fields, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(canonical.encode()).hexdigest() if fields else ''


def configuration_status(home, cookie, now=None):
    config = read_json(Path(home) / 'config.json')
    account = config.get('account') or {}
    if not isinstance(account, dict):
        account = {}
    try:
        age = (time.time() if now is None else now) - float(account.get('verified_at', 0))
    except (TypeError, ValueError):
        age = -1
    bound = bool(cookie and config.get('credential_fingerprint') == fingerprint(cookie))
    verified = bool(bound and account.get('account_id') and account.get('nickname') and 0 <= age < 86400)
    confirmed = bool(verified and config.get('confirmed_account_id') == account['account_id'])
    return {'config_present': bool(config), 'login_verified': verified,
            'account_verified': verified, 'account_confirmed': confirmed,
            'account_id': account.get('account_id') if verified else None,
            'nickname': account.get('nickname') if verified else None,
            'verified_at': account.get('verified_at') if verified else None,
            'configuration_complete': confirmed}


def save_confirmation(home, cookie, account):
    private_json(Path(home) / 'config.json', {
        'version': 1, 'account': account, 'confirmed_account_id': account['account_id'],
        'credential_fingerprint': fingerprint(cookie), 'confirmed_at': time.time(),
    })


def require_confirmed_account(cookie):
    """Recheck the SAME credential immediately before an upload, without QR fallback."""
    from cookie_manager import verify_account
    config = read_json(home_path() / 'config.json')
    if not cookie or config.get('credential_fingerprint') != fingerprint(cookie) or not config.get('confirmed_account_id'):
        raise ValueError('请先运行 configure，在配置页登录并确认发布账号。')
    account = verify_account(cookie)
    if account['account_id'] != config['confirmed_account_id']:
        raise ValueError('当前登录账号与确认的账号不一致，请重新运行 configure。')
    expected = os.environ.get('XHS_ACCOUNT_ID')
    if expected and expected != account['account_id']:
        raise ValueError('采集/发布账号配置与实际登录账号不一致。')
    return account
