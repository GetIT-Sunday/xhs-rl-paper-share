"""Contract, privacy and account-boundary tests, using synthetic platform responses."""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import account_state
import configure
import cookie_manager
import paper2xhs
import publish_to_xhs


class ConfigurationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name)
        self.cookie = 'a1=test;web_session=SECRET_SENTINEL'
        self.account = {'account_id': 'synthetic-account', 'nickname': '科研账号', 'avatar': '',
                        'verified_at': time.time(), 'login_verified': True}
        self.env = patch.dict(os.environ, {'PAPER2XHS_HOME': str(self.home), 'XHS_COOKIE_CACHE': str(self.home/'cookie.json')})
        self.env.start()
        self.old_cookie = os.environ.pop('XHS_COOKIE', None)
        self.old_id = os.environ.pop('XHS_ACCOUNT_ID', None)

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def test_private_storage_and_binding_expiry(self):
        self.assertFalse(account_state.configuration_status(self.home, self.cookie)['configuration_complete'])
        account_state.save_confirmation(self.home, self.cookie, self.account)
        self.assertEqual((self.home/'config.json').stat().st_mode & 0o777, 0o600)
        self.assertNotIn('SECRET_SENTINEL', (self.home/'config.json').read_text())
        self.assertTrue(account_state.configuration_status(self.home, self.cookie)['configuration_complete'])
        self.assertFalse(account_state.configuration_status(self.home, 'another-cookie')['configuration_complete'])
        self.assertFalse(account_state.configuration_status(self.home, self.cookie, now=time.time()+86401)['configuration_complete'])

    def test_guard_rechecks_actual_identity_before_upload(self):
        with self.assertRaises(ValueError):
            account_state.require_confirmed_account(self.cookie)
        account_state.save_confirmation(self.home, self.cookie, self.account)
        with patch.object(cookie_manager, 'verify_account', return_value=self.account) as probe:
            self.assertEqual(account_state.require_confirmed_account(self.cookie)['account_id'], 'synthetic-account')
            probe.assert_called_once_with(self.cookie)
        with patch.object(cookie_manager, 'verify_account', return_value={**self.account, 'account_id': 'different'}):
            with self.assertRaises(ValueError):
                account_state.require_confirmed_account(self.cookie)

    def test_cookie_serialization_preserves_binding(self):
        self.assertEqual(account_state.fingerprint('a1=test;web_session=secret'),
                         account_state.fingerprint('web_session=secret; a1=test'))

    def test_external_cookie_change_blocks_confirmation(self):
        wizard = configure.Wizard(self.home, self.home/'cookie.json')
        wizard.cookie, wizard.account = self.cookie, self.account
        account_state.private_json(wizard.cache, {'cookie': 'a1=other;web_session=other'})
        with patch.object(configure, 'verify_account') as verify:
            wizard.work('confirm')
        verify.assert_not_called()
        self.assertFalse(wizard.complete)
        self.assertFalse((self.home/'config.json').exists())

    def test_upload_blocked_without_account_confirmation(self):
        client = MagicMock(cookie=self.cookie)
        with contextlib.redirect_stdout(io.StringIO()):
            result = publish_to_xhs.publish_note(client, {}, 'unused.png')
        self.assertFalse(result['success'])
        client.get_upload_files_permit.assert_not_called()
        client.post.assert_not_called()

    def test_confirmation_requires_platform_identity_and_explicit_action(self):
        wizard = configure.Wizard(self.home, self.home/'cookie.json')
        wizard.cookie = self.cookie
        account_state.private_json(wizard.cache, {'cookie': self.cookie})
        wizard.dependencies = {'xhs': True}
        with self.assertRaises(cookie_manager.LoginError):
            wizard.start('confirm')
        with patch.object(configure, 'verify_account', return_value=self.account):
            wizard.work('verify')
            self.assertTrue(wizard.snapshot()['account_verified'])
            self.assertFalse(wizard.snapshot()['configuration_complete'])
            self.assertFalse((self.home/'config.json').exists())
            wizard.work('confirm')
        self.assertTrue(wizard.snapshot()['configuration_complete'])
        self.assertNotIn('SECRET_SENTINEL', json.dumps(wizard.snapshot()))
        self.assertNotIn('SECRET_SENTINEL', wizard.status_file.read_text())
        self.assertEqual(wizard.status_file.stat().st_mode & 0o777, 0o600)
        with patch.object(configure, 'verify_account', side_effect=RuntimeError(self.cookie)):
            wizard.work('verify')
        self.assertFalse(wizard.snapshot()['configuration_complete'])
        self.assertFalse(account_state.configuration_status(self.home, self.cookie)['configuration_complete'])
        self.assertNotIn('SECRET_SENTINEL', wizard.status_file.read_text())

    def test_qr_completion_persists_cookie_but_does_not_confirm_account(self):
        wizard = configure.Wizard(self.home, self.home/'cookie.json')
        qr = MagicMock(deadline=time.time()+120)
        qr.image.return_value = b'fake-image'
        qr.poll.return_value = ('logged_in', self.cookie)
        with patch.object(configure, 'QRLogin', return_value=qr), patch.object(configure, 'verify_account', return_value=self.account), patch.object(wizard.stop, 'wait', return_value=False):
            wizard.work('login')
        self.assertTrue(wizard.snapshot()['account_verified'])
        self.assertFalse(wizard.snapshot()['configuration_complete'])
        self.assertEqual(account_state.read_json(self.home/'cookie.json')['cookie'], self.cookie)
        self.assertEqual((self.home/'cookie.json').stat().st_mode & 0o777, 0o600)

    def test_switch_during_confirmation_requires_another_confirmation(self):
        wizard = configure.Wizard(self.home, self.home/'cookie.json')
        wizard.cookie, wizard.account = self.cookie, self.account
        account_state.private_json(wizard.cache, {'cookie': self.cookie})
        with patch.object(configure, 'verify_account', return_value={**self.account, 'account_id': 'other'}):
            wizard.work('confirm')
        self.assertFalse(wizard.complete)
        self.assertEqual(wizard.account['account_id'], 'other')

    def test_self_identity_rejects_public_missing_and_guest_data(self):
        client = MagicMock()
        for result in ({'nickname': 'name'}, {'user_id': 'a'}, {'user_id': 'a', 'nickname': 'Guest', 'guest': True}):
            client.get_self_info2.return_value = result
            with patch.object(cookie_manager, '_make_client', return_value=client), self.assertRaises(cookie_manager.LoginError):
                cookie_manager.verify_account(self.cookie)
        client.get_self_info2.return_value = {'user_id': 'a', 'nickname': 'name', 'avatar': 'javascript:evil'}
        with patch.object(cookie_manager, '_make_client', return_value=client):
            self.assertEqual(cookie_manager.verify_account(self.cookie)['avatar'], '')

    def test_http_token_host_origin_expiry_and_redaction(self):
        wizard = configure.Wizard(self.home, self.home/'cookie.json')
        wizard.cookie = self.cookie
        with configure.Server(wizard) as server:
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                self.assertEqual(server.server_address[0], '127.0.0.1')
                with urlopen(server.origin) as response:
                    html = response.read().decode()
                    self.assertIn('配置你的科研账号', html)
                    self.assertNotIn(wizard.token, html)
                    self.assertEqual(response.headers['Referrer-Policy'], 'no-referrer')
                for headers in ({}, {'X-Paper2XHS-Token': 'bad'}, {'X-Paper2XHS-Token': wizard.token, 'Origin': 'https://evil.example'}, {'X-Paper2XHS-Token': wizard.token, 'Host': 'evil.example'}):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(server.origin+'/api/status', headers=headers))
                    self.assertEqual(error.exception.code, 403)
                req = Request(server.origin+'/api/status', headers={'X-Paper2XHS-Token': wizard.token})
                with urlopen(req) as response:
                    data = response.read().decode()
                    self.assertNotIn('SECRET_SENTINEL', data)
                    self.assertNotIn(wizard.token, data)
                wizard.expires_at = time.time()-1
                with self.assertRaises(HTTPError) as error:
                    urlopen(req)
                self.assertEqual(error.exception.code, 410)
            finally:
                server.shutdown()
                worker.join()

    def test_transport_never_prints_raw_login_response_and_signs_get_correctly(self):
        try:
            import xhs
            import xhshow
        except ImportError:
            self.skipTest('SDK transport needs installed runtime dependencies')
        with patch.object(xhshow, 'Xhshow') as signer:
            client = cookie_manager._make_client(self.cookie)
            response = MagicMock(status_code=200)
            response.json.return_value = {'success': True, 'data': {'secret': self.cookie}}
            output = io.StringIO()
            with patch.object(client.session, 'request', return_value=response), contextlib.redirect_stdout(output):
                client.get('/api/example', params={'id': 'a'})
            self.assertEqual(output.getvalue(), '')
            signer.return_value.sign_headers_get.assert_called_once()
            signer.return_value.sign_headers_post.assert_not_called()
            response.json.side_effect = ValueError('empty upload body')
            with patch.object(client.session, 'request', return_value=response):
                self.assertIs(client.request('PUT', 'https://ros-upload.xiaohongshu.com/test'), response)


if __name__ == '__main__':
    unittest.main()
