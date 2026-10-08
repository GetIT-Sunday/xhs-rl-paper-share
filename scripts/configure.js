'use strict';
const $ = id => document.getElementById(id);
const token = new URLSearchParams(location.hash.slice(1)).get('token') || sessionStorage.getItem('paper2xhs-token') || '';
if (token) sessionStorage.setItem('paper2xhs-token', token);
history.replaceState(null, '', '/');
let lastQr = null, imageUrl = null, stopped = false;
async function api(path, method = 'GET') {
  const response = await fetch('/api/' + path, {method, headers: {'X-Paper2XHS-Token': token}, cache: 'no-store'});
  if (!response.ok) {
    const error = await response.json();
    if ([403, 410].includes(response.status)) stopped = true;
    throw new Error(error.error || '请求未完成，请重试。');
  }
  return path === 'qr' ? response.blob() : response.json();
}
function render(s) {
  $('home').textContent = s.home;
  $('python').textContent = '已就绪'; $('python').className = 'ok';
  $('dependencies').textContent = s.environment_ready ? '已就绪' : '待安装';
  $('dependencies').className = s.environment_ready ? 'ok' : '';
  $('missing').textContent = s.environment_ready ? '' : '请让 Agent 完成依赖安装，再重新打开配置页。';
  $('login-status').textContent = s.login_verified ? '已核实登录' : s.phase === 'scanned' ? '手机待确认' : '待登录';
  $('account-status').textContent = s.configuration_complete ? '已确认' : s.account_verified ? '等待你确认' : '待核对';
  $('metrics').textContent = s.metrics_mapping_configured ? '已配置 · 未验证' : '未配置';
  $('message').textContent = s.message; $('message').className = s.phase === 'error' ? 'error' : '';
  $('login').disabled = s.busy || !s.environment_ready;
  $('verify').disabled = s.busy || !s.cookie_configured || !s.environment_ready;
  $('confirm').disabled = s.busy || !s.account_verified || !s.environment_ready || s.configuration_complete;
  $('login').textContent = s.account_verified ? '切换账号' : s.phase === 'error' ? '重新生成二维码' : '生成登录二维码';
  $('account').hidden = !s.account; $('qr-area').hidden = !!s.account;
  $('section-title').textContent = s.account ? '核对发布账号' : '登录小红书';
  $('instruction').textContent = s.account ? '以下信息来自当前登录账号，请确认这是你要使用的账号。' : '使用小红书 App 扫码，并在手机上确认登录。';
  if (s.account) {
    $('nickname').textContent = s.account.nickname;
    $('account-id').textContent = '账号 ID：' + s.account.account_id;
    $('profile').href = 'https://www.xiaohongshu.com/user/profile/' + encodeURIComponent(s.account.account_id);
    $('avatar').hidden = !s.account.avatar;
    if (s.account.avatar && $('avatar').src !== s.account.avatar) $('avatar').src = s.account.avatar;
  }
  $('step-env').className = s.environment_ready ? 'done' : 'active';
  $('step-login').className = s.account_verified ? 'done' : s.environment_ready ? 'active' : '';
  $('step-account').className = s.configuration_complete ? 'done' : s.account_verified ? 'active' : '';
  $('footer-title').textContent = s.configuration_complete ? '配置完成，可以回到对话了' : '确认真实账号后即可完成';
  $('confirm').textContent = s.configuration_complete ? '已保存 · 请回到对话' : '确认账号并返回对话';
  const seconds = s.qr_expires_at ? Math.max(0, Math.ceil(s.qr_expires_at - Date.now()/1000)) : 0;
  $('countdown').textContent = s.qr_ready ? `二维码剩余 ${seconds} 秒` : '';
  $('qr-placeholder').hidden = s.qr_ready;
  $('qr').hidden = !s.qr_ready;
}
async function refresh() {
  const state = await api('status'); render(state);
  if (state.qr_ready && lastQr !== state.qr_expires_at) {
    const blob = await api('qr');
    if (imageUrl) URL.revokeObjectURL(imageUrl);
    imageUrl = URL.createObjectURL(blob); $('qr').src = imageUrl; lastQr = state.qr_expires_at;
  }
  if (!state.qr_ready) lastQr = null;
}
function failure(error) {
  $('message').textContent = error.message; $('message').className = 'error';
  if (stopped) for (const id of ['login','verify','confirm']) $(id).disabled = true;
}
for (const action of ['login', 'verify', 'confirm']) $(action).addEventListener('click', async () => {
  $(action).disabled = true;
  try { render(await api(action, 'POST')); } catch (error) { failure(error); }
});
$('avatar').addEventListener('error', () => { $('avatar').hidden = true; });
async function poll() {
  if (stopped) return;
  try { await refresh(); } catch (error) {
    if (error instanceof TypeError) { stopped = true; error = new Error('配置服务已关闭。请让 Agent 重新打开配置页；已保存的数据不会丢失。'); }
    failure(error);
  }
  if (!stopped) setTimeout(poll, 1500);
}
poll();
