#!/usr/bin/env python3
"""XHS QR login with private storage and authenticated account verification."""
from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import time
import uuid
from urllib.parse import urlsplit, parse_qsl

from account_state import current_cookie, home_path, private_json, read_json


class LoginError(ValueError):
    """Only fixed, credential-free messages may cross the UI boundary."""


def _get_cache_path():
    explicit = os.environ.get('XHS_COOKIE_CACHE')
    if explicit:
        return Path(explicit).expanduser()
    if os.environ.get('XHS_WORKSPACE'):
        return Path(os.environ['XHS_WORKSPACE']).expanduser() / '.xhs_cookie_cache.json'
    if os.environ.get('PAPER2XHS_HOME'):
        return home_path() / 'cookie.json'
    return Path.home() / '.xhs_cookie_cache.json'


COOKIE_CACHE_PATH = _get_cache_path()


def _make_client(cookie_str=''):
    try:
        from xhs import XhsClient
        from xhshow import Xhshow
    except ImportError:
        raise LoginError('登录依赖尚未就绪，请让 Agent 完成 setup 后重试。') from None

    class QuietClient(XhsClient):
        # xhs 0.2.13 prints every raw response (including login sessions).
        # Override the transport instead of globally redirecting threaded stdout.
        def request(self, method, url, **kwargs):
            try:
                response = self.session.request(method, url, timeout=self.timeout,
                                                proxies=self.proxies, **kwargs)
            except Exception:
                raise LoginError('连接小红书超时或网络不可达，请稍后重试。') from None
            if response.status_code in (461, 471):
                raise LoginError('平台要求验证，请在小红书官方页面完成验证后重试。')
            if response.status_code == 429:
                raise LoginError('平台请求频率受限，请稍后重试。')
            if response.status_code >= 500:
                raise LoginError('小红书服务暂时不可用，请稍后重试。')
            # Image uploads return an empty body or XML, not the web API envelope.
            if urlsplit(url).hostname == 'ros-upload.xiaohongshu.com':
                if 200 <= response.status_code < 300:
                    return response
                raise LoginError('图片上传失败，请稍后重试。')
            try:
                data = response.json()
            except ValueError:
                raise LoginError('平台返回非 JSON 响应，当前接口可能不可用。') from None
            if not isinstance(data, dict) or not data.get('success'):
                raise LoginError('平台拒绝请求，可能需要重新登录或更新接口适配。')
            return data.get('data', True)

    signer = Xhshow()
    client = None

    def sign_func(url, data=None, **kwargs):
        cookies = client.cookie_dict
        if data is None:
            parsed = urlsplit(url)
            return signer.sign_headers_get(uri=parsed.path, cookies=cookies,
                                           params=dict(parse_qsl(parsed.query)), x_rap=True)
        return signer.sign_headers_post(uri=url, cookies=cookies, payload=data, x_rap=True)

    client = QuietClient(cookie=cookie_str, sign=sign_func, timeout=12)
    return client


def verify_account(cookie_str):
    if not cookie_str:
        raise LoginError('尚未登录，请先扫码。')
    result = _make_client(cookie_str).get_self_info2()
    # v2 /user/me is authenticated self identity; never use public profile lookup.
    if not isinstance(result, dict) or result.get('guest') or result.get('is_guest'):
        raise LoginError('平台未返回已登录用户，请重新扫码。')
    account_id = result.get('user_id')
    nickname = result.get('nickname')
    if not isinstance(account_id, str) or not account_id or not isinstance(nickname, str) or not nickname:
        raise LoginError('登录账号字段无法核实，请更新接口适配；不会继续发布。')
    avatar = result.get('images') or result.get('image') or result.get('avatar') or ''
    if not isinstance(avatar, str) or not avatar.startswith('https://'):
        avatar = ''
    return {'account_id': account_id, 'nickname': nickname, 'avatar': avatar,
            'verified_at': time.time(), 'login_verified': True}


def _validate_cookie(cookie_str):
    try:
        verify_account(cookie_str)
        return True
    except Exception:
        return False


def _load_cache():
    return read_json(COOKIE_CACHE_PATH)


def _save_cache(cookie_str, login_time):
    private_json(COOKIE_CACHE_PATH, {'cookie': cookie_str, 'login_time': login_time})


class QRLogin:
    def __init__(self):
        self.a1 = uuid.uuid4().hex + uuid.uuid4().hex[:14]
        self.client = _make_client(f'a1={self.a1}')
        self.qr = self.client.get_qrcode()
        if not isinstance(self.qr, dict) or not all(self.qr.get(k) for k in ('qr_id', 'code', 'url')):
            raise LoginError('平台未返回有效二维码，请稍后重试。')
        self.deadline = time.time() + 120

    def image(self):
        import qrcode
        output = io.BytesIO()
        qrcode.make(self.qr['url']).save(output, format='PNG')
        return output.getvalue()

    def poll(self):
        if time.time() >= self.deadline:
            raise LoginError('二维码已过期，请重新生成。')
        result = self.client.check_qrcode(qr_id=self.qr['qr_id'], code=self.qr['code'])
        if not isinstance(result, dict):
            raise LoginError('平台返回未知扫码状态，请重新生成二维码。')
        status = result.get('code_status', 0)
        if status == 2:
            info = result.get('login_info') or {}
            # Bind to server-issued session; never treat the QR's user_id as verified identity.
            session = info.get('web_session') or info.get('secure_session') or info.get('session')
            if not isinstance(session, str) or not session or any(c in session for c in ';\r\n'):
                raise LoginError('扫码完成，但平台未返回可用登录凭证。')
            self.client.session.cookies.set('web_session', session)
            return 'logged_in', self.client.cookie
        if status not in (0, 1):
            raise LoginError('二维码已失效，请重新生成。')
        return ('scanned' if status == 1 else 'waiting'), None


def login_by_qrcode():
    login = QRLogin()
    import qrcode
    qr = qrcode.QRCode(border=1)
    qr.add_data(login.qr['url'])
    qr.print_ascii(invert=True)
    print('请用小红书 App 扫码并在手机上确认。')
    while time.time() < login.deadline:
        time.sleep(2)
        state, cookie = login.poll()
        if cookie:
            _save_cache(cookie, time.time())
            account = verify_account(cookie)
            print(f"已核实登录账号：{account['nickname']}（{account['account_id']}）。发布前请运行 configure 确认账号。")
            return cookie
    raise LoginError('扫码超时，请重新生成二维码。')


def get_valid_cookie(force_refresh=False):
    cookie = current_cookie(COOKIE_CACHE_PATH)
    if not force_refresh and _validate_cookie(cookie):
        return cookie
    return login_by_qrcode()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh', action='store_true')
    parser.add_argument('--validate', action='store_true')
    args = parser.parse_args()
    try:
        if args.validate:
            account = verify_account(current_cookie(COOKIE_CACHE_PATH))
            print(f"已核实账号：{account['nickname']}（{account['account_id']}）")
        else:
            get_valid_cookie(args.refresh)
        sys.exit(0)
    except Exception as exc:
        print(str(exc) if isinstance(exc, LoginError) else '登录未完成，请打开 configure 检查。', file=sys.stderr)
        sys.exit(1)
