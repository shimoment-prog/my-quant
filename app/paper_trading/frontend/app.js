(() => {
  'use strict';

  const main = document.getElementById('main');
  const statusLabel = document.getElementById('server-state');
  const STORAGE_KEY = 'paper-trading.selected-task';
  const statusNames = {draft: '草稿', starting: '启动中', running: '运行中', paused: '暂停开仓', manual_paused: '手动暂停', connection_paused: '行情恢复中', ending: '结束中', stopped: '已结束', error: '异常'};
  const exitNames = {rr15: '固定 1.5R', trail_ema: '1.5R 后 EMA 追踪', ema_slow: '1.5R 后 EMA 变缓退出', ema_turn: '1.5R 后 EMA 转向退出'};
  const opNames = {gt: '大于 >', gte: '大于等于 ≥', lt: '小于 <', lte: '小于等于 ≤', cross_up: '上穿', cross_down: '下穿', between: '位于区间', bullish: 'K线收涨（阳线）', bearish: 'K线收跌（阴线）', wick_above: '整根K在线上方', wick_below: '整根K在线下方'};
  const sourceNames = {open: '开盘价', high: '最高价', low: '最低价', close: '收盘价', volume: '成交量'};
  const reasonNames = {stop: '止损', stop_loss: '止损', stop_gap: '跳空止损', target: '固定止盈', take_profit: '固定止盈', ema_slow_close: 'EMA变缓', ema_turn_close: 'EMA转向', manual_close: '手动平仓', manual_stop: '手动平仓并结束', close: '手动平仓', long_exit: '多单平仓条件', short_exit: '空单平仓条件'};
  const state = {
    bootstrap: null, tasks: [], view: 'task', taskId: null, detail: null,
    tab: 'trades', selectedTrade: null, taskRequest: 0, taskBusy: false,
    taskError: '', actionBusy: false, deletingTaskId: null, deletedTaskIds: new Set(), search: '', tradeFilter: 'all',
    showRsi: true, showPositions: true, wizard: null, editor: null,
    charts: null, shellTaskId: null, tabSignature: null, tabUi: new Map(), history: null, focusRequest: 0,
    lastListRefresh: 0, lastBootstrapRefresh: 0,
  };
  try { state.taskId = localStorage.getItem(STORAGE_KEY); } catch (_) { /* Storage is optional. */ }
  const clone = value => JSON.parse(JSON.stringify(value));
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
  const finite = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const number = (value, digits = 2) => finite(value) ? Number(value).toLocaleString('en-US', {minimumFractionDigits: digits, maximumFractionDigits: digits}) : '—';
  const price = value => finite(value) ? Number(value).toLocaleString('en-US', {maximumFractionDigits: 8}) : '—';
  const signed = value => finite(value) ? `${Number(value) > 0 ? '+' : ''}${number(value)}` : '—';
  const pnlClass = value => finite(value) ? Number(value) > 0 ? 'positive' : Number(value) < 0 ? 'negative' : '' : '';
  const msDate = value => finite(value) && Number(value) > 0 ? new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'}).format(new Date(Number(value))) : '—';
  const fullDate = value => finite(value) && Number(value) > 0 ? new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'}).format(new Date(Number(value))) : '—';
  const statusBadge = status => `<span class="status ${esc(status)}"><i class="status-dot"></i>${esc(statusNames[status] || status || '未知')}</span>`;
  const displayStatus = task => {
    if ((task.end_requested || task.pause_reason === 'ending') && task.status !== 'stopped') return 'ending';
    if (task.status === 'paused') {
      if (task.pause_reason === 'manual' || task.manual_paused) return 'manual_paused';
      if (task.pause_reason === 'connection') return 'connection_paused';
    }
    return task.status;
  };
  const selectedOptions = (items, selected) => items.map(item => { const [value, label] = Array.isArray(item) ? item : [item, item]; return `<option value="${esc(value)}"${String(value) === String(selected) ? ' selected' : ''}>${esc(label)}</option>`; }).join('');
  const jsonBlock = object => `<pre class="json-block">${esc(JSON.stringify(object, null, 2))}</pre>`;
  const inputField = (label, name, value, attrs = '', hint = '') => `<label class="field"><span>${esc(label)}</span><input data-wizard="${esc(name)}" value="${esc(value)}" ${attrs}>${hint ? `<small>${esc(hint)}</small>` : ''}</label>`;
  const detailItem = (label, value, cls = '') => `<div class="detail-item ${cls}"><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`;
  let toastTimer;

  function notify(message, error = false) {
    const toast = document.getElementById('toast');
    toast.textContent = message; toast.hidden = false; toast.classList.toggle('error', error);
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { toast.hidden = true; }, error ? 9000 : 5000);
  }

  async function api(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 25000);
    try {
      const response = await fetch(path, {...options, cache: 'no-store', signal: controller.signal, headers: {'Content-Type': 'application/json', ...options.headers}});
      const contentType = response.headers.get('Content-Type') || '';
      const payload = contentType.includes('json') ? await response.json() : {error: await response.text()};
      if (!response.ok) throw new Error(payload.error || `请求失败（HTTP ${response.status}）`);
      return payload;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('后台响应超时，请检查服务与网络。');
      if (error instanceof TypeError) throw new Error('无法连接本地后台，请确认服务仍在运行。');
      throw error;
    } finally { clearTimeout(timer); }
  }

  function strategies() { return state.bootstrap?.strategies || []; }
  function strategyById(id) { return strategies().find(item => item.id === id); }
  function taskStrategy(task) { return task?.config?.strategy || task?.strategy || {}; }
  function canDeleteTask(data) { return Boolean(data?.task && ['draft', 'stopped'].includes(data.task.status) && !data.position && !data.pending_order); }
  function rememberTask() {
    try { if (state.taskId) localStorage.setItem(STORAGE_KEY, state.taskId); else localStorage.removeItem(STORAGE_KEY); } catch (_) { /* Optional preference. */ }
  }

  function renderSidebar() {
    document.getElementById('task-count').textContent = state.tasks.length;
    document.getElementById('library-nav').setAttribute('aria-pressed', state.view === 'library' || state.view === 'editor');
    const query = state.search.trim().toLowerCase();
    const items = state.tasks.filter(task => `${task.name} ${task.symbol} ${task.interval} ${taskStrategy(task).name || ''}`.toLowerCase().includes(query));
    document.getElementById('task-list').innerHTML = items.length ? items.map(task => {
      const strategy = taskStrategy(task), account = task.account || {};
      return `<button type="button" class="task-item" data-task-id="${esc(task.id)}" aria-pressed="${state.view === 'task' && state.taskId === task.id}"><strong>${esc(task.name)}</strong><span class="task-meta">${esc(task.symbol)} · ${esc(task.interval)}${strategy.name ? ` · ${esc(strategy.name)}` : ''}</span><span class="task-state"><span class="${task.status === 'error' ? 'negative' : task.status === 'running' && !task.end_requested ? 'positive' : 'muted'}">${esc(statusNames[displayStatus(task)] || task.status)}</span>${finite(account.equity) ? `<span class="tabular">${number(account.equity)} U</span>` : ''}</span></button>`;
    }).join('') : `<p class="sidebar-empty">${query ? '没有匹配的任务。' : '还没有模拟任务。点击“新建”配置第一个任务。'}</p>`;
  }

  function renderEmpty(message = '') {
    destroyCharts(); state.shellTaskId = null;
    main.innerHTML = `<div class="page-empty"><span class="pill">独立账户 · 实时模拟</span><h1>${message ? '暂时无法连接后台' : '从一个模拟任务开始'}</h1><p>${esc(message || '选择策略、币种与周期，设置资金。各任务独立运行，图表和交易记录互不混用。')}</p><div class="actions">${message ? '<button class="button button-primary" data-action="refresh">重新连接</button>' : '<button class="button button-primary" data-action="new-task">＋ 创建模拟任务</button><button class="button" data-action="library">浏览策略库</button>'}</div></div>`;
  }

  async function bootstrap(initial = false) {
    try {
      const data = await api('/api/bootstrap');
      data.tasks = (data.tasks || []).filter(task => !state.deletedTaskIds.has(task.id));
      state.bootstrap = data; state.tasks = data.tasks; state.lastBootstrapRefresh = Date.now();
      statusLabel.textContent = data.market?.error ? '后台已连接 · 行情目录待恢复' : '后台已连接 · 公开行情';
      statusLabel.classList.toggle('is-error', Boolean(data.market?.error));
      statusLabel.title = data.market?.error || '模拟资金在本地记账，不连接交易账户。';
      if (data.app?.name) document.title = `${data.app.name} · 策略验证工作台`;
      renderSidebar();
      if (initial) {
        if (!state.tasks.some(task => task.id === state.taskId)) state.taskId = state.tasks[0]?.id || null;
        if (state.taskId) openTask(state.taskId); else renderEmpty();
      }
      return true;
    } catch (error) {
      statusLabel.textContent = '后台未连接'; statusLabel.classList.add('is-error'); statusLabel.title = error.message;
      if (initial) renderEmpty(error.message); else notify(error.message, true);
      return false;
    }
  }

  async function refreshTaskList() {
    try {
      const data = await api('/api/tasks');
      state.tasks = (data.tasks || []).filter(task => !state.deletedTaskIds.has(task.id)); state.lastListRefresh = Date.now(); renderSidebar();
    } catch (_) { /* The selected task connection displays failures without replacing its last valid data. */ }
  }

  function openTask(id) {
    if (state.deletedTaskIds.has(id)) return;
    if (state.view === 'task' && state.taskId === id && state.detail) { loadTask(true); return; }
    state.view = 'task'; state.taskId = id; state.detail = null; state.taskError = '';
    state.selectedTrade = null; state.tab = 'trades'; state.taskRequest++; state.taskBusy = false;
    state.tabUi.clear(); state.focusRequest++; state.history = newHistory(id);
    state.shellTaskId = null; destroyCharts(); rememberTask(); renderSidebar();
    main.innerHTML = '<div class="page-empty"><span class="loading-dot"></span><h1>正在读取任务</h1><p>加载该任务的独立账户、图表与交易记录。</p></div>';
    loadTask(true);
  }

  async function loadTask(force = false) {
    if (!state.taskId || state.view !== 'task' || state.deletingTaskId === state.taskId || state.deletedTaskIds.has(state.taskId) || (state.taskBusy && !force)) return;
    const id = state.taskId, request = ++state.taskRequest; state.taskBusy = true;
    try {
      const data = await api(`/api/tasks/${encodeURIComponent(id)}`);
      if (request !== state.taskRequest || state.taskId !== id || state.view !== 'task') return;
      state.detail = data; state.taskError = '';
      updateTaskView();
    } catch (error) {
      if (request !== state.taskRequest || state.taskId !== id || state.view !== 'task') return;
      state.taskError = error.message;
      if (state.detail) updateTaskView();
      else main.innerHTML = `<div class="page-empty"><h1>任务暂时不可用</h1><p>${esc(error.message)}</p><button class="button" data-action="retry-task">重新读取</button></div>`;
    } finally { if (request === state.taskRequest) state.taskBusy = false; }
  }

  function taskShell() {
    saveTabUi(document.getElementById('tab-content'));
    destroyCharts();
    state.tabSignature = null;
    main.innerHTML = `<section id="task-header"></section><div id="task-notice" class="gap-small"></div><section id="kpi-grid" class="kpis" aria-label="当前任务账户摘要"></section><section class="panel chart-panel"><div class="chart-toolbar"><div><h3 id="chart-title"></h3><span id="chart-live-label" class="chart-live-label"></span></div><div class="chart-tools"><label class="checkbox-label"><input type="checkbox" data-toggle="positions" ${state.showPositions ? 'checked' : ''}>交易仓位</label><label class="checkbox-label"><input type="checkbox" data-toggle="rsi" ${state.showRsi ? 'checked' : ''}>RSI</label><button id="history-button" class="button button-small" data-action="chart-history">加载更早K线</button><button class="button button-small" data-action="chart-latest">返回最新</button></div></div><div id="chart-legend" class="chart-legend"></div><div id="history-status" class="chart-history-status" role="status"></div><div id="price-wrap" class="chart-price-wrap"><div id="price-chart" class="price-chart"></div><div id="chart-empty" class="chart-empty"><strong>等待真实行情</strong><span>启动任务后加载历史预热与实时K线。</span></div><svg id="trade-overlay" class="trade-overlay" aria-label="本任务多空交易仓位图"></svg></div><div id="rsi-wrap" class="rsi-wrap"><div id="rsi-chart" class="rsi-chart"></div></div><p class="chart-note">“信号”标记指向刚收盘的关键K；“成交多 / 成交空”标记对应实际开仓所在K，平仓另标“平”。K线标签为开盘时间，详情记录实际信号与成交时间。未收盘指标随行情变化，仅供预览；信号仍收盘确认。</p></section><div class="tabs" role="tablist" aria-label="任务详情">${[['trades', '交易明细'], ['account', '账户'], ['config', '规则与配置'], ['logs', '日志']].map(([id, label]) => `<button class="tab" id="tab-${id}" data-tab="${id}" role="tab" aria-controls="tab-content" aria-selected="${state.tab === id}">${label}</button>`).join('')}</div><section id="tab-content" class="tab-content" role="tabpanel" aria-labelledby="tab-${state.tab}"></section>`;
    createCharts();
  }

  function updateTaskView() {
    const data = state.detail, task = data.task, account = data.account || {}, strategy = taskStrategy(task);
    if (state.shellTaskId !== task.id) { state.shellTaskId = task.id; taskShell(); }
    const busy = state.actionBusy ? ' disabled' : '';
    const ending = Boolean(task.end_requested || task.pause_reason === 'ending');
    const manualPause = task.pause_reason === 'manual' || task.manual_paused;
    const connectionPause = task.status === 'paused' && task.pause_reason === 'connection' && !manualPause && !ending;
    let buttons = `<button class="button" data-action="copy-task"${busy}>复制配置</button>`;
    if (task.status === 'draft') buttons += `<button class="button" data-action="edit-draft"${busy}>继续配置</button><button class="button button-primary" data-action="task-start"${busy}>启动模拟</button>`;
    if ((task.status === 'running' || connectionPause) && !ending) buttons += `<button class="button" data-action="task-pause"${busy}>暂停开新仓</button>`;
    if (task.status === 'paused' && !ending && !connectionPause) buttons += `<button class="button button-primary" data-action="task-resume"${state.actionBusy || task.connection?.status !== 'connected' ? ' disabled' : ''}${task.connection?.status !== 'connected' ? ' title="行情恢复正常后才能手动恢复开仓"' : ''}>恢复开新仓</button>`;
    if (task.status === 'error' && !ending) buttons += `<button class="button" data-action="task-start"${busy}>重试连接 / 恢复初始化</button>`;
    if (['running', 'paused', 'error'].includes(task.status) && !ending) buttons += `<button class="button" data-action="task-stop"${busy}>结束任务</button>`;
    if (data.position || data.pending_order) buttons += `<button class="button button-danger" data-action="task-close"${busy}>平仓并结束</button>`;
    if (canDeleteTask(data)) buttons += `<button class="button button-danger" data-action="delete-task"${busy}>${state.deletingTaskId === task.id ? '正在删除…' : '删除任务'}</button>`;
    document.getElementById('task-header').innerHTML = `<div class="eyebrow">独立模拟任务 / ${esc(task.symbol)} · ${esc(task.interval)}</div><div class="row"><div class="actions"><h1>${esc(task.name)}</h1>${statusBadge(displayStatus(task))}</div><div class="actions">${buttons}</div></div><p class="subtitle">${esc(strategy.name || '策略')} · v${esc(strategy.version || '—')} · ${strategy.kind === 'manual' ? '手动策略' : '代码策略'}${strategy.params?.prior_bars ? ` · N=${esc(strategy.params.prior_bars)}` : ''}${strategy.params?.exit_model ? ` · ${esc(exitNames[strategy.params.exit_model] || strategy.params.exit_model)}` : ''} · ${task.started_at_ms ? `开始于 ${fullDate(task.started_at_ms)}` : '尚未启动'}</p>`;
    const connection = task.connection || {};
    let notice = '';
    if (state.taskError) notice = `<div class="notice error">页面与后台连接中断：${esc(state.taskError)} 下方保留最后一次成功读取的数据。</div>`;
    else if (task.status === 'draft') notice = '<div class="notice">这是已保存的草稿。启动后才会接收行情并等待新的实时交易信号；历史预热不会补开历史订单。</div>';
    else if (connectionPause) notice = `<div class="notice warning">行情恢复中：${esc(connection.message || '正在重新连接并补齐K线。')} 恢复后自动等待新信号，缺口不补交易。此时点击“暂停开新仓”可改为手动暂停。</div>`;
    else if (task.status === 'paused' && manualPause && !ending) notice = `<div class="notice${connection.status !== 'connected' ? ' warning' : ''}">已手动暂停开新仓；现有持仓继续管理。${connection.status === 'connected' ? '需要继续开仓时，请点击“恢复开新仓”。' : `行情仍在恢复，连接正常后才能手动恢复。${esc(connection.message || '')}`}</div>`;
    else if (connection.message || !['connected', 'live', 'ok', 'healthy', 'running'].includes(connection.status)) notice = `<div class="notice ${task.status === 'error' || connection.status === 'error' ? 'error' : 'warning'}">${esc(connection.message || (task.status === 'stopped' ? '任务已结束，保留账户与历史记录。' : '正在等待或恢复行情。'))}</div>`;
    if (data.pending_order) notice += '<div class="notice gap-small">有模拟订单等待后续有效实时报价成交。信号价与最终模拟成交价可能不同。</div>';
    if (data.pending_exit || (task.end_requested && data.position)) notice += `<div class="notice gap-small">${data.pending_exit ? '已请求平仓，等待下一笔有效实时报价。' : '已停止开新仓；现有持仓退出后结束任务。'}</div>`;
    document.getElementById('task-notice').innerHTML = notice;
    document.getElementById('kpi-grid').innerHTML = [
      ['当前权益', account.equity, '余额 + 浮动盈亏', ''], ['账户余额', account.balance, '含已发生费用的资金余额', ''],
      ['已实现净盈亏', account.realized_pnl, '已平仓交易，扣除双边费用', pnlClass(account.realized_pnl)], ['浮动盈亏', account.unrealized_pnl, '未平仓仓位，不计入闭单胜率', pnlClass(account.unrealized_pnl)],
    ].map(([label, value, hint, cls]) => `<div class="kpi" title="${esc(hint)}"><span class="kpi-label">${label} · USDT</span><strong class="kpi-value ${cls}">${label.includes('盈亏') ? signed(value) : number(value)}</strong><small>${hint}</small></div>`).join('');
    document.getElementById('chart-title').textContent = `${task.symbol} · ${task.interval} · 策略运行周期`;
    document.getElementById('chart-live-label').textContent = `最近行情 ${msDate(task.last_quote_time_ms || connection.last_event_ms)} · 最近确认K ${msDate(task.last_bar_time_ms)}`;
    updateCharts(data);
    renderTab();
  }

  function renderTab() {
    if (!state.detail || !document.getElementById('tab-content')) return;
    for (const button of main.querySelectorAll('[data-tab]')) button.setAttribute('aria-selected', button.dataset.tab === state.tab);
    const container = document.getElementById('tab-content'); container.setAttribute('aria-labelledby', `tab-${state.tab}`);
    const data = state.detail;
    const quote = data.position ? [data.metadata?.last_price, data.metadata?.last_quote_timestamp_ms, data.task.connection?.status, data.task.recovery_in_progress, state.taskError] : null;
    const relevant = state.tab === 'trades' ? [data.trades, data.position, quote, state.tradeFilter, state.selectedTrade] : state.tab === 'config' ? [data.task.config, data.task.status] : state.tab === 'logs' ? data.logs : [data.account, data.equity, data.position];
    const signature = `${data.task.id}:${state.tab}:${JSON.stringify(relevant)}`;
    if (state.tabSignature === signature) return;
    saveTabUi(container);
    state.tabSignature = signature;
    container.dataset.uiOwner = `${data.task.id}:${state.tab}`;
    if (state.tab === 'trades') renderTrades(container);
    else if (state.tab === 'account') renderAccount(container);
    else if (state.tab === 'config') renderConfig(container);
    else renderLogs(container);
    restoreTabUi(container);
  }

  function elementUiKey(element) {
    if (element.dataset.uiKey) return element.dataset.uiKey;
    const scope = element.closest('[data-ui-scope]')?.dataset.uiScope || 'task';
    const detail = element.tagName === 'DETAILS' ? element : element.closest('details');
    const detailKey = detail ? detail.dataset.uiKey || `${scope}:${detail.querySelector('summary')?.textContent || ''}` : `${scope}:main`;
    return `${element.tagName}:${detailKey}:${element.classList.contains('table-wrap') ? 'table' : element.classList.contains('json-block') ? 'json' : 'detail'}`;
  }

  function saveTabUi(container) {
    const owner = container?.dataset.uiOwner;
    if (!owner || !owner.startsWith(`${state.taskId}:`)) return;
    const saved = state.tabUi.get(owner) || {details: new Map(), scroll: new Map()};
    for (const element of container.querySelectorAll('details')) saved.details.set(elementUiKey(element), element.open);
    for (const element of container.querySelectorAll('.table-wrap,.json-block')) saved.scroll.set(elementUiKey(element), {left: element.scrollLeft, top: element.scrollTop});
    state.tabUi.set(owner, saved);
  }

  function restoreTabUi(container) {
    const saved = state.tabUi.get(container.dataset.uiOwner); if (!saved) return;
    for (const element of container.querySelectorAll('details')) if (saved.details.has(elementUiKey(element))) element.open = saved.details.get(elementUiKey(element));
    for (const element of container.querySelectorAll('.table-wrap,.json-block')) {
      const position = saved.scroll.get(elementUiKey(element));
      if (position) { element.scrollLeft = position.left; element.scrollTop = position.top; }
    }
  }

  function currentTradeQuote(data = state.detail) {
    const value = data?.metadata?.last_price, time = data?.metadata?.last_quote_timestamp_ms;
    if (!finite(value) || Number(value) <= 0 || !finite(time) || Number(time) <= 0) return {value: null, time: null, label: '等待实时报价'};
    const label = state.taskError ? '最近报价 · 后台未连接' : data.task.connection?.status !== 'connected' || data.task.recovery_in_progress ? '最近报价 · 行情恢复中' : '最新报价';
    return {value: Number(value), time: Number(time), label};
  }

  function renderTrades(container) {
    const data = state.detail;
    const quote = currentTradeQuote(data);
    let trades = [...(data.trades || [])];
    if (data.position && !trades.some(trade => trade.id === data.position.id)) trades.push({...data.position, status: 'open'});
    const filtered = trades.filter(trade => state.tradeFilter === 'all' || trade.status === state.tradeFilter).sort((a, b) => Number(b.entry_time_ms || 0) - Number(a.entry_time_ms || 0));
    container.innerHTML = `<div class="table-toolbar"><div class="actions"><h3>逐笔交易 <span class="muted">${trades.length}</span></h3><select aria-label="筛选交易状态" data-trade-filter>${selectedOptions([['all', '全部交易'], ['open', '持仓中'], ['closed', '已平仓']], state.tradeFilter)}</select></div><a class="button button-small" href="/api/tasks/${encodeURIComponent(data.task.id)}/trades.csv" download>导出 CSV</a></div>${filtered.length ? `<div class="table-wrap"><table><thead><tr>${['交易 / 方向', '开仓时间', '开仓价', '当前价格', '初始 / 当前止损', '止盈 / 激活价', '平仓时间', '平仓价 / 原因', '数量 / 保证金', '双边费用', '净盈亏 · U', '结果', '平仓后余额'].map(label => `<th>${label}</th>`).join('')}</tr></thead><tbody>${filtered.map(trade => {
      const open = trade.status === 'open' || !trade.exit_time_ms;
      const targetLabel = trade.target !== null && trade.target !== undefined ? price(trade.target) : `${price(trade.activation_level)}<span class="table-subtext">激活位 · 无固定止盈</span>`;
      const net = open ? null : trade.net_pnl;
      const currentPrice = open ? `${price(quote.value)}<span class="table-subtext">${esc(quote.label)}${quote.time ? ` · ${msDate(quote.time)}` : ''}</span>` : '—';
      return `<tr class="trade-row" data-trade-id="${esc(trade.id)}" tabindex="0" aria-selected="${state.selectedTrade === trade.id}"><td>#${esc(shortId(trade.id))}<span class="table-subtext ${trade.side === 'long' ? 'positive' : 'negative'}">${trade.side === 'long' ? '做多' : '做空'}${open ? ' · 持仓中' : ''}</span></td><td>${msDate(trade.entry_time_ms)}</td><td>${price(trade.entry_fill)}<span class="table-subtext">信号 ${price(trade.entry_reference)}</span></td><td>${currentPrice}</td><td>${price(trade.initial_stop)}<span class="table-subtext">当前 ${price(trade.stop ?? trade.initial_stop)}</span></td><td>${targetLabel}</td><td>${open ? '—' : msDate(trade.exit_time_ms)}</td><td>${open ? '—' : price(trade.exit_fill)}<span class="table-subtext">${open ? '持仓中' : esc(reasonNames[trade.exit_reason] || trade.exit_reason || '—')}</span></td><td>${price(trade.quantity)}<span class="table-subtext">${number(trade.margin_used)} U</span></td><td>${number(Number(trade.entry_fee || 0) + Number(trade.exit_fee || 0), 4)}</td><td class="${pnlClass(net)}">${open ? '未结算' : signed(net)}</td><td class="${pnlClass(net)}">${open ? '持仓中' : finite(net) ? Number(net) > 0 ? 'Win' : Number(net) < 0 ? 'Loss' : 'Flat' : '—'}</td><td>${open ? '—' : number(trade.balance_after)}</td></tr>`;
    }).join('')}</tbody></table></div>` : '<div class="panel empty"><h3>当前没有交易记录</h3><p>任务运行后，满足策略条件才会产生实时模拟订单。</p></div>'}<p class="form-note">Win / Loss 以已平仓净盈亏判断；持仓中的浮动盈亏单独展示，不计入胜率。点击交易行定位图表。</p><div id="trade-detail"></div>`;
    const selected = trades.find(trade => trade.id === state.selectedTrade);
    if (selected) renderTradeDetail(selected);
  }

  function shortId(id) { const text = String(id ?? ''); return text.length > 12 ? text.slice(-8) : text; }

  function renderTradeDetail(trade) {
    const node = document.getElementById('trade-detail'); if (!node) return;
    node.dataset.uiScope = trade.id;
    const history = trade.stop_history || [];
    const quote = currentTradeQuote(), open = trade.status === 'open' || !trade.exit_time_ms;
    const liveDetails = open ? `${detailItem('当前价格', price(quote.value))}${detailItem(quote.label, fullDate(quote.time))}` : '';
    node.innerHTML = `<section class="details-panel"><div class="row"><h3>#${esc(shortId(trade.id))} · ${trade.side === 'long' ? '多单' : '空单'}明细</h3><button class="button button-small" data-action="focus-trade">定位K线</button></div><div class="detail-grid">${detailItem('信号确认时间', fullDate(trade.signal_time_ms))}${detailItem('模拟开仓时间', fullDate(trade.entry_time_ms))}${detailItem('信号参考价', price(trade.entry_reference))}${detailItem('模拟开仓价', price(trade.entry_fill))}${liveDetails}${detailItem('初始止损 / 当前止损', `${price(trade.initial_stop)} / ${price(trade.stop ?? trade.initial_stop)}`)}${detailItem('固定止盈', trade.target == null ? '无固定止盈' : price(trade.target))}${detailItem('退出激活价', price(trade.activation_level))}${detailItem('数量 / 名义金额', `${price(trade.quantity)} / ${number(trade.entry_notional)} U`)}${detailItem('平仓时间', fullDate(trade.exit_time_ms))}${detailItem('模拟平仓价 / 原因', `${price(trade.exit_fill)} / ${reasonNames[trade.exit_reason] || trade.exit_reason || '持仓中'}`)}${detailItem('开仓费 / 平仓费', `${number(trade.entry_fee, 4)} / ${number(trade.exit_fee, 4)} U`)}${detailItem('毛盈亏 / 净盈亏', `${signed(trade.gross_pnl)} / ${signed(trade.net_pnl)} U`)}</div>${history.length ? `<details class="gap-small"><summary>查看止损变化（按生效时间展示）</summary><div class="table-wrap gap-small"><table><thead><tr><th>生效时间</th><th>止损价</th><th>原因</th></tr></thead><tbody>${history.map(item => `<tr><td>${msDate(stopTime(item, trade.entry_time_ms))}</td><td>${price(item.stop)}</td><td>${esc(item.reason || '止损更新')}</td></tr>`).join('')}</tbody></table></div></details>` : ''}<details class="gap-small"><summary>查看完整信号条件与指标审计</summary>${jsonBlock(trade.audit || {message: '此笔交易没有附加条件审计。'})}</details></section>`;
  }

  function renderAccount(container) {
    const account = state.detail.account || {};
    const stats = [['初始本金 · U', number(account.initial_capital)], ['占用保证金 · U', number(account.margin_used)], ['可用资金 · U', number(account.available_balance)], ['累计费用 · U', number(account.fees_paid, 4)], ['已平仓 / 盈利 / 亏损', `${account.closed_count ?? '—'} / ${account.winning_count ?? '—'} / ${account.losing_count ?? '—'}`], ['闭单胜率', finite(account.win_rate) ? `${number(account.win_rate)}%` : '—'], ['权益收益率', finite(account.return_percent) ? `${signed(account.return_percent)}%` : '—'], ['最大回撤', finite(account.max_drawdown_percent) ? `${number(account.max_drawdown_percent)}%` : '—']];
    if (!container.querySelector('#account-stats')) container.innerHTML = '<div id="account-stats" class="stats-grid"></div><section class="panel gap"><h3>当前任务权益曲线</h3><div id="equity-chart" class="equity-chart"></div><p class="form-note">仅包含该任务的账户记录；回撤采样口径见“规则与配置”。</p></section><div id="account-position"></div>';
    document.getElementById('account-stats').innerHTML = stats.map(([label, value]) => `<div class="stat-card"><span>${label}</span><strong>${esc(value)}</strong></div>`).join('');
    document.getElementById('account-position').innerHTML = state.detail.position ? `<details class="panel gap"><summary>当前持仓详情</summary>${jsonBlock(state.detail.position)}</details>` : '<p class="form-note">当前没有未平仓仓位。</p>';
    drawEquity();
  }

  function renderConfig(container) {
    const task = state.detail.task, config = task.config || {}, strategy = config.strategy || {}, account = config.account || {};
    container.innerHTML = `<section class="panel"><div class="row"><h3>本次运行配置快照</h3><button class="button button-small" data-action="${task.status === 'draft' ? 'edit-draft' : 'copy-task'}">${task.status === 'draft' ? '编辑草稿' : '复制为新任务调整'}</button></div><dl class="summary-list gap"><dt>策略</dt><dd>${esc(strategy.name || strategy.id)} · v${esc(strategy.version || '—')} · ${strategy.kind === 'manual' ? '网页手动编排' : '代码接入'}</dd><dt>币种 / 周期</dt><dd>${esc(task.symbol)} / ${esc(task.interval)}</dd><dt>本金</dt><dd>${number(account.initial_capital)} USDT · 当前任务独享</dd><dt>每笔配置</dt><dd>${account.sizing === 'notional' ? '名义金额' : '保证金'} ${number(account.order_amount)} USDT × ${price(account.leverage)} 倍杠杆</dd><dt>手续费 / 滑点</dt><dd>单边 ${price(account.fee_percent)}% / ${price(account.slippage_ticks)} ticks</dd><dt>创建 / 启动</dt><dd>${fullDate(task.created_at_ms)} / ${fullDate(task.started_at_ms)}</dd></dl><details class="gap"><summary>查看完整规则及参数快照</summary>${jsonBlock(config)}</details></section><section class="panel gap"><h3>模拟成交与统计口径</h3><p class="subtitle">${esc(state.bootstrap?.app?.execution_note || '收盘确认信号后，使用后续有效实时报价模拟成交。')}</p><ul class="form-note"><li>以实际收到的交易价格事件检查止盈止损；信号参考价与模拟成交价分别记录。</li><li>历史K线用于预热；不将启动之前的历史交易记作实时模拟交易。</li><li>单边手续费与滑点按该任务配置计入；当前模型未计永续资金费、标记价触发及强平。</li><li>开仓保证金与杠杆通过仓位数量体现，盈亏不会再次乘以杠杆。</li><li>行情重连并补齐K线后自动等待新信号；手动暂停需要手动恢复；缺口不补交易。</li><li>断线和恢复情况记录在日志；无法完整观测的价格路径应结合数据质量记录判断。</li></ul>${state.detail.metadata ? `<details class="gap-small"><summary>数据来源、运行与统计元信息</summary>${jsonBlock(state.detail.metadata)}</details>` : ''}</section>`;
  }

  function renderLogs(container) {
    const logs = [...(state.detail.logs || [])].sort((a, b) => Number(b.time_ms) - Number(a.time_ms));
    container.innerHTML = `<div class="row"><h3>本任务运行日志</h3><span class="muted" style="font-size:11px">最近 ${logs.length} 条</span></div><div class="log-list gap-small">${logs.length ? logs.map(log => `<article class="log-item"><time>${msDate(log.time_ms)}</time><span class="log-type">${esc(log.type)}</span><p>${esc(log.message)}</p>${log.data && Object.keys(log.data).length ? `<details data-ui-key="log-${esc(log.id || `${log.time_ms}-${log.type}-${log.message}`)}"><summary>事件数据</summary>${jsonBlock(log.data)}</details>` : ''}</article>`).join('') : '<div class="empty">当前没有运行日志。启动后的行情、信号与订单事件将显示在这里。</div>'}</div>`;
  }

  function renderLibrary() {
    leaveTaskView('library'); renderSidebar();
    main.innerHTML = `<div class="eyebrow">策略库 / 可复用规则</div><div class="row"><h1>保存规则，独立验证</h1><button class="button button-primary" data-action="new-strategy">＋ 创建简单策略</button></div><p class="subtitle">手动策略用普通表单编排；复杂策略通过代码接入。每次运行固定自己的规则快照。</p><div class="library-grid gap">${strategies().map(strategy => `<section class="panel strategy-card"><div><span class="pill">${strategy.kind === 'manual' ? '手动策略' : '代码部署'} · v${esc(strategy.version)}</span></div><h3>${esc(strategy.name)}</h3><p>${esc(strategy.description || (strategy.kind === 'manual' ? manualSummary(strategy.definition) : '已接入的代码策略，在创建任务时配置公开参数。'))}</p><div class="actions"><button class="button button-primary" data-use-strategy="${esc(strategy.id)}">创建模拟任务</button>${strategy.kind === 'manual' ? `<button class="button" data-edit-strategy="${esc(strategy.id)}">${strategy.id.startsWith('builtin_') ? '编辑并另存' : '编辑为新版本'}</button>` : ''}<button class="button button-small" data-inspect-strategy="${esc(strategy.id)}">规则详情</button></div><div id="strategy-detail-${esc(strategy.id)}" hidden></div></section>`).join('') || '<div class="panel empty">策略库暂时没有已保存的策略。可以先创建简单策略。</div>'}</div><section class="notice gap">“同向交叉关键K”保留交叉前连续同向、交叉后等待关键K及分阶段退出，使用代码模板。手动编辑器中的同根交叉条件不是这套复杂策略的替代品。</section>`;
  }

  function leaveTaskView(view) { state.view = view; state.taskRequest++; state.taskBusy = false; state.shellTaskId = null; destroyCharts(); }

  function beginWizard({strategyId, task = null, edit = false} = {}) {
    const config = task?.config || {};
    const strategy = strategyById(strategyId || config.strategy?.id) || strategies()[0];
    state.wizard = {
      step: 0, editId: edit ? task.id : null,
      name: task ? `${task.name}${edit ? '' : ' · 对照'}` : '',
      symbol: task?.symbol || (state.bootstrap?.market?.symbols || []).find(item => item.symbol === 'ETHUSDT')?.symbol || state.bootstrap?.market?.symbols?.[0]?.symbol || '',
      interval: task?.interval || '4h', strategyId: strategy?.id || '',
      strategySnapshot: config.strategy ? clone(config.strategy) : null,
      params: clone(config.strategy?.params || {prior_bars: 3, exit_model: 'rr15'}),
      account: clone(config.account || state.bootstrap?.defaults?.account || {}), error: '', busy: false,
    };
    leaveTaskView('wizard'); renderSidebar(); renderWizard();
  }

  function wizardStrategy() {
    const wizard = state.wizard;
    if (wizard.strategySnapshot?.id === wizard.strategyId) return wizard.strategySnapshot;
    return strategyById(wizard.strategyId);
  }

  function renderWizard() {
    const wizard = state.wizard, labels = ['选择策略', '币种与周期', '资金与成本', '核对并启动'];
    main.innerHTML = `<div class="eyebrow">${wizard.editId ? '继续配置草稿' : '创建模拟任务'} / 独立账户</div><div class="row"><h1>配置一次，独立运行</h1><button class="button" data-action="cancel-wizard" ${wizard.busy ? 'disabled' : ''}>取消</button></div><div class="stepper">${labels.map((label, i) => `<div class="step" ${wizard.step === i ? 'aria-current="step"' : ''}><b>${i + 1}</b>${label}</div>`).join('')}</div><div class="panel wizard-body">${wizardBody()}</div>${wizard.error ? `<div class="form-error" role="alert">${esc(wizard.error)}</div>` : ''}<div class="wizard-footer"><button class="button" data-action="wizard-back" ${wizard.step === 0 || wizard.busy ? 'disabled' : ''}>上一步</button><div class="actions">${wizard.step === 3 ? `<button class="button" data-action="save-draft" ${wizard.busy ? 'disabled' : ''}>保存草稿</button><button class="button button-primary" data-action="start-new" ${wizard.busy ? 'disabled' : ''}>${wizard.busy ? '正在保存…' : '保存并启动模拟'}</button>` : `<button class="button button-primary" data-action="wizard-next">下一步</button>`}</div></div><p class="form-note">策略条件与资金配置分别保存。启动前仅保存草稿，不产生模拟订单。</p>`;
  }

  function wizardBody() {
    const wizard = state.wizard, strategy = wizardStrategy(), account = wizard.account;
    if (wizard.step === 0) return `<h3>选择一个已保存的策略版本</h3><div class="choice-grid">${strategies().map(item => `<button class="choice" data-wizard-strategy="${esc(item.id)}" aria-pressed="${wizard.strategyId === item.id}"><span class="pill">${item.kind === 'manual' ? '网页手动编排' : '代码策略'} · v${esc(item.version)}</span><strong>${esc(item.name)}</strong><p>${esc(item.description || (item.kind === 'manual' ? manualSummary(item.definition) : '使用完整代码规则，公开参数可在下方配置。'))}</p></button>`).join('')}</div>${!strategies().length ? '<p class="form-note">请先到策略库创建一个简单策略。</p><button class="button gap-small" data-action="new-strategy">创建简单策略</button>' : ''}${strategy?.kind === 'code' ? `<div class="field-grid gap"><label class="field"><span>交叉前连续同向根数 N</span><select data-wizard-param="prior_bars">${selectedOptions([3, 4, 5, 6, 7, 8, 9, 10], wizard.params.prior_bars)}</select><small>含交叉当根实际检查 N+1 次变化；下一根起寻找关键K。</small></label><label class="field"><span>退出方式</span><select data-wizard-param="exit_model">${selectedOptions(Object.entries(exitNames), wizard.params.exit_model)}</select><small>四种退出独立运行，保留代码策略完整语义。</small></label></div><p class="form-note">固定指标：橙色 EMA10、白色 SMA10、Wilder RSI14。斜率与等待状态由代码处理。</p>` : strategy ? `<div class="notice gap">${esc(manualSummary(strategy.definition))}</div><p class="form-note">需要改变交易条件时，在策略库保存新版本；资金与币种在后续步骤配置。</p>` : ''}`;
    if (wizard.step === 1) {
      const symbols = state.bootstrap?.market?.symbols || [];
      return `<h3>选择验证市场</h3><div class="field-grid gap"><label class="field"><span>币种 · Binance USDT 永续</span><input data-wizard="symbol" list="contract-symbols" value="${esc(wizard.symbol)}" placeholder="例如 ETHUSDT" autocomplete="off" maxlength="30"><datalist id="contract-symbols">${symbols.map(item => `<option value="${esc(item.symbol)}">${esc(item.base_asset || '')}</option>`).join('')}</datalist><small>${symbols.length ? `可搜索 ${symbols.length} 个公开合约；仅做模拟交易。` : '行情目录暂不可用，可填写合约代码，启动时由后台核验。'}</small></label><label class="field"><span>策略运行周期</span><select data-wizard="interval">${selectedOptions(state.bootstrap?.intervals || ['1m', '5m', '15m', '30m', '1h', '4h', '1d'], wizard.interval)}</select><small>指标周期以当前K线根数计算，不是日历天。</small></label></div><div class="gap">${inputField('任务名称', 'name', wizard.name, 'maxlength="80" placeholder="例如 ETH · 均线对照A"')}</div>${state.bootstrap?.market?.error ? `<div class="notice warning gap">行情目录状态：${esc(state.bootstrap.market.error)}</div>` : ''}`;
    }
    if (wizard.step === 2) return `<h3>设置这个任务的独立资金</h3><div class="field-grid gap">${inputField('初始本金 · USDT', 'account.initial_capital', account.initial_capital, 'type="number" min="0.01" step="any"')}<label class="field"><span>每笔金额的含义</span><select data-wizard="account.sizing">${selectedOptions([['margin', '每笔保证金'], ['notional', '每笔目标名义金额']], account.sizing || 'margin')}</select><small>保证金 × 杠杆 = 目标名义金额。</small></label>${inputField(`${account.sizing === 'notional' ? '每笔目标名义金额' : '每笔保证金'} · USDT`, 'account.order_amount', account.order_amount, 'type="number" min="0.01" step="any"')}${inputField('杠杆 · 倍', 'account.leverage', account.leverage, 'type="number" min="1" step="1"')}${inputField('单边手续费 · %', 'account.fee_percent', account.fee_percent, 'type="number" min="0" max="99" step="any"', '例如 0.05 表示单边万分之五。')}${inputField('不利滑点 · ticks', 'account.slippage_ticks', account.slippage_ticks, 'type="number" min="0" step="1"', '按当前合约最小价格跳动计算。')}</div><div id="sizing-preview" class="notice gap">${sizingPreview(account)}</div><p class="form-note">每笔金额固定，不随账户盈利自动复利。最终数量按合约步长向下取整；资金不足时记录拒单原因。</p>`;
    return `<h3>核对本次独立实验</h3><dl class="summary-list gap"><dt>任务名称</dt><dd>${esc(wizard.name)}</dd><dt>策略 / 版本</dt><dd>${esc(strategy?.name || '')} · v${esc(strategy?.version || '')} · ${strategy?.kind === 'manual' ? '手动编排' : '代码部署'}</dd><dt>市场 / 周期</dt><dd>${esc(wizard.symbol)} / ${esc(wizard.interval)}</dd><dt>交易规则</dt><dd>${esc(strategy?.kind === 'code' ? `N=${wizard.params.prior_bars} · ${exitNames[wizard.params.exit_model]}` : manualSummary(strategy?.definition))}</dd><dt>独立本金</dt><dd>${number(account.initial_capital)} USDT</dd><dt>每笔配置</dt><dd>${account.sizing === 'notional' ? '名义金额' : '保证金'} ${number(account.order_amount)} USDT · ${price(account.leverage)} 倍杠杆</dd><dt>实际资金含义</dt><dd>${sizingPreview(account)}</dd><dt>单边费用</dt><dd>手续费 ${price(account.fee_percent)}% · 不利滑点 ${price(account.slippage_ticks)} ticks</dd></dl><div class="notice gap">${esc(state.bootstrap?.app?.execution_note || '启动后接入实时行情，历史仅做预热；收盘信号在下一笔有效报价模拟成交。')} 当前不计资金费、标记价触发和强平。</div><p class="form-note">保存草稿仅记录设置；启动后后台独立运行。关闭网页不会停止仍在运行的后台。</p>`;
  }

  function sizingPreview(account) {
    const amount = Number(account.order_amount), leverage = Number(account.leverage);
    const notional = account.sizing === 'notional' ? amount : amount * leverage;
    const margin = account.sizing === 'notional' ? amount / leverage : amount;
    return `目标保证金 ${number(margin)} U · 目标名义金额 ${number(notional)} U（数量取整前）`;
  }

  function validateWizard(step = state.wizard.step) {
    const wizard = state.wizard, account = wizard.account;
    if (step >= 0 && !wizardStrategy()) return '请选择一个已保存的策略。';
    if (step >= 1) {
      if (!wizard.name.trim()) return '请填写任务名称。';
      if (!/^[A-Z0-9]+USDT$/.test(wizard.symbol)) return '请填写大写的 USDT 永续合约代码，例如 ETHUSDT。';
      if (!(state.bootstrap?.intervals || []).includes(wizard.interval)) return '请选择支持的K线周期。';
    }
    if (step >= 2) {
      for (const key of ['initial_capital', 'order_amount', 'leverage']) if (!finite(account[key]) || Number(account[key]) <= 0) return '本金、每笔金额和杠杆必须大于0。';
      if (!finite(account.fee_percent) || Number(account.fee_percent) < 0 || Number(account.fee_percent) >= 100) return '手续费须介于0%（含）与100%之间。';
      if (!Number.isInteger(Number(account.slippage_ticks)) || Number(account.slippage_ticks) < 0) return '滑点须为大于等于0的整数 ticks。';
    }
    return '';
  }

  async function saveTask(start) {
    const wizard = state.wizard, error = validateWizard(3);
    if (error) { wizard.error = error; renderWizard(); return; }
    const selected = wizardStrategy();
    const strategy = {id: selected.id, kind: selected.kind, name: selected.name, version: selected.version, params: selected.kind === 'code' ? clone(wizard.params) : {}};
    if (selected.kind === 'manual') strategy.definition = clone(selected.definition);
    const body = {name: wizard.name.trim(), symbol: wizard.symbol, interval: wizard.interval, strategy, account: clone(wizard.account), start: start && !wizard.editId};
    wizard.busy = true; wizard.error = ''; renderWizard();
    try {
      const result = await api(wizard.editId ? `/api/tasks/${encodeURIComponent(wizard.editId)}` : '/api/tasks', {method: wizard.editId ? 'PUT' : 'POST', body: JSON.stringify(body)});
      const id = result.id || result.task?.id || wizard.editId;
      if (!id) throw new Error('后台未返回任务编号。');
      if (start && wizard.editId) await api(`/api/tasks/${encodeURIComponent(id)}/action`, {method: 'POST', body: JSON.stringify({action: 'start'})});
      await refreshTaskList(); openTask(id); notify(start ? '任务已提交启动。行情与订单状态将在任务面板显示。' : '草稿已保存，尚未启动模拟交易。');
    } catch (failure) { wizard.busy = false; wizard.error = failure.message; if (state.view === 'wizard') renderWizard(); }
  }

  function defaultDefinition() {
    return {
      indicators: [{id: 'ema', type: 'EMA', length: 10, source: 'close'}, {id: 'sma', type: 'SMA', length: 10, source: 'close'}, {id: 'rsi', type: 'RSI', length: 14, source: 'close'}],
      long: {enabled: true, logic: 'all', conditions: [{left: 'ema', op: 'cross_up', right: 'sma'}, {left: 'rsi', op: 'gt', right: 50}]},
      short: {enabled: true, logic: 'all', conditions: [{left: 'ema', op: 'cross_down', right: 'sma'}, {left: 'rsi', op: 'lt', right: 50}]},
      long_exit: {enabled: false, logic: 'all', conditions: []}, short_exit: {enabled: false, logic: 'all', conditions: []},
      exit: {stop_type: 'percent', stop_percent: 1, stop_indicator: 'ema', reward_risk: 1.5},
    };
  }

  function beginEditor(id = null) {
    const existing = id ? strategyById(id) : null;
    const builtin = Boolean(existing?.id?.startsWith('builtin_'));
    state.editor = {id: builtin ? null : existing?.id || null, name: existing ? `${existing.name}${builtin ? ' · 自定义' : ''}` : '我的双均线策略', definition: clone(existing?.definition || defaultDefinition()), error: '', busy: false};
    const definition = state.editor.definition;
    for (const key of ['long', 'short', 'long_exit', 'short_exit']) if (!definition[key]) definition[key] = {enabled: false, logic: 'all', conditions: []};
    leaveTaskView('editor'); renderSidebar(); renderEditor();
  }

  function indicatorLabel(indicator) { return `${indicator.type}${indicator.length} · ${sourceNames[indicator.source] || indicator.source}`; }
  function references(definition = state.editor?.definition) { return [...Object.entries(sourceNames), ...(definition?.indicators || []).map(item => [item.id, indicatorLabel(item)])]; }
  function refLabel(ref, definition) { return typeof ref === 'number' ? String(ref) : references(definition).find(([id]) => id === ref)?.[1] || String(ref ?? ''); }
  function conditionText(condition, definition) {
    if (condition.op === 'bullish') return 'K线收涨（收盘价 > 开盘价）';
    if (condition.op === 'bearish') return 'K线收跌（收盘价 < 开盘价）';
    if (condition.op === 'wick_above' || condition.op === 'wick_below') return `整根K${condition.op === 'wick_above' ? '严格高于' : '严格低于'} ${refLabel(condition.right, definition)}（含影线，触线不合格）`;
    if (condition.op === 'between') return `${refLabel(condition.left, definition)} 位于 ${condition.include_lower === false ? '(' : '['}${condition.right}, ${condition.upper}${condition.include_upper === false ? ')' : ']'}`;
    return `${refLabel(condition.left, definition)} ${opNames[condition.op] || condition.op} ${refLabel(condition.right, definition)}`;
  }
  function manualSummary(definition) {
    if (!definition) return '简单指标条件策略。';
    const names = (definition.indicators || []).map(item => `${item.type}${item.length}`).join(' / ');
    return `${names}；多单 ${definition.long?.enabled ? definition.long.conditions?.length || 0 : 0} 条、空单 ${definition.short?.enabled ? definition.short.conditions?.length || 0 : 0} 条开仓条件；${definition.exit?.stop_type === 'indicator' ? '指标止损' : `${definition.exit?.stop_percent ?? '—'}% 止损`}、${definition.exit?.reward_risk ?? '—'}R 止盈。`;
  }

  function ruleGroup(key, title) {
    const definition = state.editor.definition, group = definition[key], refs = references(definition);
    return `<section class="panel"><div class="rule-group-heading"><label class="checkbox-label"><input type="checkbox" data-group-enabled="${key}" ${group.enabled ? 'checked' : ''}>${title}</label><select aria-label="${title}组合方式" data-group-logic="${key}">${selectedOptions([['all', '全部满足 AND'], ['any', '任意满足 OR']], group.logic)}</select></div><div class="${!group.enabled ? 'disabled-group' : ''}">${group.conditions.map((condition, index) => {
      const attrs = `data-condition-group="${key}" data-condition-index="${index}"`;
      const unary = ['bullish', 'bearish'].includes(condition.op), wick = ['wick_above', 'wick_below'].includes(condition.op);
      let right = '';
      if (condition.op === 'between') right = `<div class="range-fields"><input type="number" step="any" aria-label="区间下界" ${attrs} data-condition-field="right" value="${esc(condition.right)}"><input type="number" step="any" aria-label="区间上界" ${attrs} data-condition-field="upper" value="${esc(condition.upper)}"><div class="range-options"><label class="checkbox-label"><input type="checkbox" ${attrs} data-condition-field="include_lower" ${condition.include_lower !== false ? 'checked' : ''}>含下界</label><label class="checkbox-label"><input type="checkbox" ${attrs} data-condition-field="include_upper" ${condition.include_upper !== false ? 'checked' : ''}>含上界</label></div></div>`;
      else if (!unary) right = `<div class="condition-right"><select aria-label="条件右值来源" ${attrs} data-condition-field="right_source">${selectedOptions([['__number', '数值'], ...refs], typeof condition.right === 'number' ? '__number' : condition.right)}</select>${typeof condition.right === 'number' ? `<input type="number" step="any" aria-label="条件数值" ${attrs} data-condition-field="right" value="${esc(condition.right)}">` : ''}</div>`;
      else right = '<span class="condition-hint">收盘确认</span>';
      return `<div class="condition-row">${unary || wick ? '<span class="condition-hint">当前整根K线</span>' : `<select aria-label="条件左值" ${attrs} data-condition-field="left">${selectedOptions(refs, condition.left)}</select>`}<select aria-label="条件关系" ${attrs} data-condition-field="op">${selectedOptions(Object.entries(opNames), condition.op)}</select>${right}<button class="button" aria-label="移除此条件" data-remove-condition="${key}:${index}">×</button></div>`;
    }).join('')}<button class="button button-small gap-small" data-add-condition="${key}">＋ 添加条件</button></div></section>`;
  }

  function renderEditor() {
    const editor = state.editor, definition = editor.definition;
    main.innerHTML = `<div class="eyebrow">策略库 / ${editor.id ? '保存新版本' : '创建手动策略'}</div><div class="row"><h1>简单策略编辑器</h1><button class="button" data-action="library" ${editor.busy ? 'disabled' : ''}>返回策略库</button></div><p class="subtitle">通过指标和条件行定义简单规则。所有条件按同一根已确认K线判断；不包含连续同向或交叉后等待状态。</p><label class="field editor-title-field gap"><span>策略名称</span><input data-editor-name value="${esc(editor.name)}" maxlength="80"></label><div class="editor-layout"><section class="panel"><h3>使用的指标</h3><div class="indicator-head"><span>指标</span><span>周期 / 根</span><span>价格来源</span><span></span></div>${definition.indicators.map((indicator, index) => `<div class="indicator-row"><select data-indicator-index="${index}" data-indicator-field="type" aria-label="指标类型">${selectedOptions(['EMA', 'SMA', 'RSI'], indicator.type)}</select><input type="number" min="1" max="500" step="1" data-indicator-index="${index}" data-indicator-field="length" value="${esc(indicator.length)}" aria-label="指标周期"><select data-indicator-index="${index}" data-indicator-field="source" aria-label="指标价格来源">${selectedOptions(Object.entries(sourceNames).filter(([id]) => id !== 'volume'), indicator.source)}</select><button class="button button-small" data-remove-indicator="${index}" aria-label="移除指标">×</button></div>`).join('')}<button class="button button-small gap-small" data-action="add-indicator">＋ 添加指标</button><p class="form-note">OHLC及成交量可直接用于条件。首版提供EMA、SMA、RSI；名称随周期显示，条件引用保持关联。</p></section><section class="panel"><h3>止损与固定止盈</h3><div class="field-grid gap-small"><label class="field"><span>初始止损方式</span><select data-exit-field="stop_type">${selectedOptions([['percent', '距开仓价固定百分比'], ['indicator', '信号K的指标价位']], definition.exit.stop_type)}</select></label>${definition.exit.stop_type === 'indicator' ? `<label class="field"><span>止损参考指标</span><select data-exit-field="stop_indicator">${selectedOptions(definition.indicators.filter(item => item.type !== 'RSI').map(item => [item.id, indicatorLabel(item)]), definition.exit.stop_indicator)}</select></label>` : `<label class="field"><span>止损距离 · %</span><input type="number" min="0.001" step="any" data-exit-field="stop_percent" value="${esc(definition.exit.stop_percent)}"></label>`}<label class="field"><span>固定止盈 · R</span><input type="number" min="0.01" step="any" data-exit-field="reward_risk" value="${esc(definition.exit.reward_risk)}"></label></div><p class="form-note">初始止损在开仓时固定；止盈按初始风险R计算。每个任务同时只持一笔。复杂分阶段退出使用代码策略。</p></section></div><div class="editor-layout">${ruleGroup('long', '做多开仓')}${ruleGroup('short', '做空开仓')}${ruleGroup('long_exit', '多单条件平仓（可选）')}${ruleGroup('short_exit', '空单条件平仓（可选）')}</div><section class="notice gap">条件组采用单层“全部满足 / 任意满足”。“整根K在线上方”比较最低价，“整根K在线下方”比较最高价，均为严格比较且包含影线。</section><section class="panel gap"><h3>规则预览</h3><div id="rule-preview" class="editor-preview gap-small"></div></section>${editor.error ? `<div class="form-error" role="alert">${esc(editor.error)}</div>` : ''}<div class="wizard-footer"><p class="form-note">保存形成策略版本，已有任务继续使用启动时的快照。</p><button class="button button-primary" data-action="save-strategy" ${editor.busy ? 'disabled' : ''}>${editor.busy ? '正在保存…' : editor.id ? '保存为新版本' : '保存策略'}</button></div>`;
    updateRulePreview();
  }

  function updateRulePreview() {
    const target = document.getElementById('rule-preview'); if (!target) return;
    const definition = state.editor.definition;
    target.textContent = [['long', '做多开仓'], ['short', '做空开仓'], ['long_exit', '多单条件平仓'], ['short_exit', '空单条件平仓']].map(([key, title]) => `${title}：${definition[key].enabled ? definition[key].conditions.length ? definition[key].conditions.map(condition => conditionText(condition, definition)).join(definition[key].logic === 'all' ? '，并且 ' : '，或者 ') : '请添加至少一个条件' : '未启用'}`).join('\n');
  }

  async function saveStrategy() {
    const editor = state.editor, definition = editor.definition;
    if (!editor.name.trim()) { editor.error = '请填写策略名称。'; renderEditor(); return; }
    if (!definition.long.enabled && !definition.short.enabled) { editor.error = '请至少启用一个开仓方向。'; renderEditor(); return; }
    for (const key of ['long', 'short', 'long_exit', 'short_exit']) if (definition[key].enabled && !definition[key].conditions.length) { editor.error = '已启用的条件组至少需要一个条件。'; renderEditor(); return; }
    for (const item of definition.indicators) if (!Number.isInteger(Number(item.length)) || Number(item.length) < 1 || Number(item.length) > 500) { editor.error = '指标周期必须为1～500的整数。'; renderEditor(); return; }
    if (!finite(definition.exit.stop_percent) || Number(definition.exit.stop_percent) <= 0 || Number(definition.exit.stop_percent) >= 100 || !finite(definition.exit.reward_risk) || Number(definition.exit.reward_risk) <= 0) { editor.error = '止损百分比须大于0且小于100，止盈R须大于0。'; renderEditor(); return; }
    if (definition.exit.stop_type === 'indicator' && !definition.indicators.some(item => item.id === definition.exit.stop_indicator && ['EMA', 'SMA'].includes(item.type))) { editor.error = '指标止损需要选择一个EMA或SMA价格指标。'; renderEditor(); return; }
    editor.busy = true; editor.error = ''; renderEditor();
    try {
      const result = await api(editor.id ? `/api/strategies/${encodeURIComponent(editor.id)}` : '/api/strategies', {method: 'POST', body: JSON.stringify({name: editor.name.trim(), definition})});
      await bootstrap(); renderLibrary(); notify(`已保存策略${result.version ? ` v${result.version}` : ''}，可以创建独立模拟任务。`);
    } catch (error) { editor.busy = false; editor.error = error.message; if (state.view === 'editor') renderEditor(); }
  }

  function safeColor(value) { return typeof value === 'string' && /^(#[\da-f]{3,8}|[a-z]+|rgba?\([\d\s.,%]+\))$/i.test(value) ? value : '#b894e7'; }
  function indicatorColor(indicator) { return !chartTheme().dark && ['#d8e2f0', '#ffffff', '#fff', 'white'].includes(String(indicator.color).toLowerCase()) ? '#77859d' : safeColor(indicator.color); }
  function chartTheme() {
    const style = getComputedStyle(document.documentElement);
    const dark = document.documentElement.dataset.theme ? document.documentElement.dataset.theme === 'dark' : matchMedia('(prefers-color-scheme: dark)').matches;
    return {background: dark ? '#181f2b' : '#ffffff', text: dark ? '#9fadc2' : '#65748b', grid: dark ? '#2a3547' : '#edf0f5', border: dark ? '#303d51' : '#dfe5ef', dark, style};
  }

  function chartOptions(container, height) {
    const theme = chartTheme();
    return {width: container.clientWidth || 600, height, layout: {background: {type: 'solid', color: theme.background}, textColor: theme.text, fontSize: 10, attributionLogo: false}, grid: {vertLines: {color: theme.grid}, horzLines: {color: theme.grid}}, rightPriceScale: {borderColor: theme.border, minimumWidth: 64}, timeScale: {borderColor: theme.border, timeVisible: true, secondsVisible: false, rightOffset: 5, tickMarkFormatter: time => new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23'}).format(new Date(Number(time) * 1000))}, localization: {locale: 'zh-CN', timeFormatter: time => fullDate(Number(time) * 1000)}, crosshair: {mode: 0}, handleScroll: {vertTouchDrag: false}};
  }

  function chartPriceFormat(data) {
    const symbol = state.bootstrap?.market?.symbols?.find(item => item.symbol === data?.task?.symbol);
    const tick = Number(data?.metadata?.price_tick_size ?? symbol?.tick_size);
    if (!Number.isFinite(tick) || tick <= 0) return {type: 'price', precision: 2, minMove: 0.01};
    // Number() removes trailing zeroes; account for tiny ticks written as 1e-8.
    const [coefficient, exponent = '0'] = String(tick).toLowerCase().split('e');
    const precision = Math.max(0, (coefficient.split('.')[1]?.length || 0) - Number(exponent));
    return {type: 'price', precision, minMove: tick};
  }

  function renderChartLegend(context = state.charts) {
    const node = document.getElementById('chart-legend'), cache = state.history;
    if (!node || !context || state.charts !== context || cache?.taskId !== context.taskId) return;
    if (context.hoverTime !== null && !cache.candles.has(context.hoverTime)) {
      context.hoverTime = null; context.hoverPane = null;
    }
    const hovered = context.hoverTime !== null;
    let time = hovered ? context.hoverTime : undefined;
    if (!hovered) for (let index = context.candleData.length - 1; index >= 0; index--) {
      if (!context.candleData[index].context_only) { time = context.candleData[index].time; break; }
    }
    const label = time === undefined ? '' : `<span>${hovered ? 'K线' : '最新'} · ${esc(msDate(time * 1000))}</span>`;
    const markup = label + context.indicators.map(item => {
      const saved = cache.indicators.get(item.id), value = saved?.values.get(time);
      const preview = finite(value) && saved?.previewTimes?.has(time);
      return `<span><i style="background:${indicatorColor(item)}"></i>${esc(item.name || item.id)} ${price(value)}${preview ? '<small class="indicator-preview-badge">盘中</small>' : ''}</span>`;
    }).join('');
    if (node.innerHTML !== markup) node.innerHTML = markup;
  }

  function chartCrosshairMove(context, pane, event) {
    if (state.charts !== context || state.history?.taskId !== context.taskId || context.sync || context.updating) return;
    const time = typeof event.time === 'number' && Number.isFinite(event.time) ? event.time : null;
    const candle = time === null ? null : state.history?.candles.get(time);
    context.hoverTime = candle && event.point && event.point.x >= 0 && event.point.y >= 0 ? time : null;
    context.hoverPane = context.hoverTime === null ? null : pane;
    renderChartLegend(context);
    context.sync = true;
    try {
      if (context.hoverTime === null) {
        context.chart.clearCrosshairPosition(); context.rsiChart.clearCrosshairPosition();
      } else if (pane === 'main') {
        const entry = [...context.lines].find(([, line]) => line.pane === 'rsi');
        const value = entry && state.history?.indicators.get(entry[0])?.values.get(context.hoverTime);
        if (entry && context.hoverTime !== null && finite(value)) context.rsiChart.setCrosshairPosition(Number(value), context.hoverTime, entry[1].series);
        else context.rsiChart.clearCrosshairPosition();
      } else context.chart.setCrosshairPosition(candle.close, context.hoverTime, context.candles);
    } finally { context.sync = false; }
  }

  function selectedTradeAutoscale(original) {
    const base = original();
    const trade = state.detail && allChartTrades(state.detail).find(item => item.id === state.selectedTrade);
    if (!trade || !state.showPositions) return base;
    const extra = [trade.entry_fill, trade.entry_reference, trade.exit_fill, trade.initial_stop, trade.stop, trade.target, trade.activation_level, ...(trade.stop_history || []).map(item => item.stop)].filter(finite).map(Number);
    if (!extra.length) return base;
    const low = Math.min(...extra, ...(base ? [base.priceRange.minValue] : []));
    const high = Math.max(...extra, ...(base ? [base.priceRange.maxValue] : []));
    return {...(base || {}), priceRange: {minValue: low, maxValue: high > low ? high : low * 1.001}};
  }

  function createCharts() {
    if (!window.LightweightCharts) { document.getElementById('chart-empty').innerHTML = '<strong>图表组件加载失败</strong><span>请刷新页面，或检查本地图表资源。</span>'; return; }
    const priceContainer = document.getElementById('price-chart'), rsiContainer = document.getElementById('rsi-chart');
    const chart = LightweightCharts.createChart(priceContainer, chartOptions(priceContainer, priceContainer.clientHeight || 360));
    const priceFormat = chartPriceFormat(state.detail);
    const candles = chart.addCandlestickSeries({priceFormat, upColor: '#12ad8b', downColor: '#e25e70', borderVisible: false, wickUpColor: '#12ad8b', wickDownColor: '#e25e70', priceLineVisible: true, lastValueVisible: true, autoscaleInfoProvider: selectedTradeAutoscale});
    const volume = chart.addHistogramSeries({priceFormat: {type: 'volume'}, priceScaleId: 'volume', lastValueVisible: false, priceLineVisible: false});
    chart.priceScale('volume').applyOptions({scaleMargins: {top: 0.85, bottom: 0}});
    const rsiChart = LightweightCharts.createChart(rsiContainer, {...chartOptions(rsiContainer, 125), rightPriceScale: {...chartOptions(rsiContainer, 125).rightPriceScale, scaleMargins: {top: 0.12, bottom: 0.12}}});
    const context = {taskId: state.detail.task.id, chart, candles, volume, rsiChart, lines: new Map(), indicators: [], hoverTime: null, hoverPane: null, updating: false, priceFormatKey: JSON.stringify(priceFormat), candleData: [], firstData: true, sync: false, equityChart: null, equitySeries: null, equityContainer: null, hitBoxes: [], resizeObserver: null};
    state.charts = context;
    chart.timeScale().subscribeVisibleLogicalRangeChange(range => { if (range && !context.sync) { context.sync = true; rsiChart.timeScale().setVisibleLogicalRange(range); context.sync = false; } scheduleOverlay(); });
    rsiChart.timeScale().subscribeVisibleLogicalRangeChange(range => { if (range && !context.sync) { context.sync = true; chart.timeScale().setVisibleLogicalRange(range); context.sync = false; } scheduleOverlay(); });
    const resize = () => {
      if (state.charts !== context) return;
      chart.resize(priceContainer.clientWidth || 600, priceContainer.clientHeight || 360);
      rsiChart.resize(rsiContainer.clientWidth || priceContainer.clientWidth || 600, 125);
      scheduleOverlay();
    };
    if (window.ResizeObserver) { context.resizeObserver = new ResizeObserver(resize); context.resizeObserver.observe(priceContainer); }
    priceContainer.addEventListener('pointermove', event => { if (event.buttons) scheduleOverlay(); });
    priceContainer.addEventListener('wheel', scheduleOverlay, {passive: true});
    chart.subscribeClick(event => { if (!event.point) return; const hit = [...context.hitBoxes].reverse().find(box => event.point.x >= box.x1 && event.point.x <= box.x2 && event.point.y >= box.y1 && event.point.y <= box.y2); if (hit) focusTrade(hit.id); });
    chart.subscribeCrosshairMove(event => chartCrosshairMove(context, 'main', event));
    rsiChart.subscribeCrosshairMove(event => chartCrosshairMove(context, 'rsi', event));
    const priceWrap = document.getElementById('price-wrap');
    for (const [container, pane] of [[priceWrap, 'main'], [rsiContainer, 'rsi']]) container.addEventListener('pointerleave', () => {
      if (context.hoverPane === pane) chartCrosshairMove(context, pane, {});
    });
    // Position drawings sit above the canvas; keep their candles inspectable.
    document.getElementById('trade-overlay').addEventListener('pointermove', event => {
      if (state.charts !== context || context.sync || context.updating) return;
      const bounds = priceWrap.getBoundingClientRect(), point = {x: event.clientX - bounds.left, y: event.clientY - bounds.top};
      const time = point.x < chart.timeScale().width() ? chart.timeScale().coordinateToTime(point.x) : null;
      chartCrosshairMove(context, 'main', {time, point});
      const candle = state.history?.candles.get(context.hoverTime);
      if (candle) {
        context.sync = true;
        try { chart.setCrosshairPosition(candle.close, context.hoverTime, candles); }
        finally { context.sync = false; }
      }
    });
  }

  function destroyCharts() {
    const context = state.charts; if (!context) return;
    context.resizeObserver?.disconnect(); context.equityChart?.remove(); context.chart.remove(); context.rsiChart.remove(); state.charts = null;
  }

  function cleanPoints(points, ohlc = false) {
    const byTime = new Map();
    for (const point of points || []) {
      if (!finite(point.time)) continue;
      if (ohlc ? !['open', 'high', 'low', 'close'].every(key => finite(point[key])) : !finite(point.value)) continue;
      byTime.set(Number(point.time), ohlc ? {...point, time: Number(point.time), open: Number(point.open), high: Number(point.high), low: Number(point.low), close: Number(point.close)} : {...point, time: Number(point.time), value: Number(point.value)});
    }
    return [...byTime.values()].sort((a, b) => a.time - b.time);
  }

  function newHistory(taskId) {
    return {taskId, candles: new Map(), indicators: new Map(), hasMore: null, busy: false, promise: null, message: '', error: ''};
  }

  function mergeChartHistory(chart, cache = state.history, replacePreview = false, previewMetadata = null) {
    if (!cache || cache.taskId !== state.taskId) return {candles: [], indicators: []};
    if (replacePreview) {
      for (const [time, candle] of cache.candles) if (candle.closed === false) cache.candles.delete(time);
      for (const saved of cache.indicators.values()) {
        for (const time of saved.previewTimes || []) saved.values.delete(time);
        saved.previewTimes = new Set();
        delete saved.preview;
      }
    }
    for (const candle of cleanPoints(chart?.candles, true)) {
      const old = cache.candles.get(candle.time);
      if (!(old?.closed && candle.closed === false)) cache.candles.set(candle.time, candle);
    }
    for (const indicator of chart?.indicators || []) {
      let saved = cache.indicators.get(indicator.id);
      if (!saved) { saved = {...indicator, values: new Map(), previewTimes: new Set()}; cache.indicators.set(indicator.id, saved); }
      if (!saved.previewTimes) saved.previewTimes = new Set();
      Object.assign(saved, {name: indicator.name, type: indicator.type, pane: indicator.pane, color: indicator.color});
      const points = [...(indicator.data || [])];
      if (indicator.preview?.confirmed === false) points.push({...indicator.preview, preview: true});
      else if (previewMetadata?.confirmed === false && finite(previewMetadata.values?.[indicator.id])) points.push({time: previewMetadata.time, value: previewMetadata.values[indicator.id], preview: true});
      for (const point of cleanPoints(points)) {
        if (point.preview === true || point.confirmed === false) {
          // A known confirmed value must never regress to a late preview.
          if (saved.values.has(point.time) && !saved.previewTimes.has(point.time)) continue;
          saved.values.set(point.time, point.value); saved.previewTimes.add(point.time);
        } else { saved.values.set(point.time, point.value); saved.previewTimes.delete(point.time); }
      }
    }
    return {candles: [...cache.candles.values()].sort((a, b) => a.time - b.time), indicators: [...cache.indicators.values()].map(indicator => ({...indicator, data: [...indicator.values].map(([time, value]) => ({time, value, ...(indicator.previewTimes.has(time) ? {preview: true} : {})})).sort((a, b) => a.time - b.time)}))};
  }

  function updateHistoryControls() {
    const button = document.getElementById('history-button'), label = document.getElementById('history-status'), cache = state.history;
    if (!button || !label || !cache || cache.taskId !== state.taskId) return;
    button.disabled = cache.busy || !cache.candles.size || cache.hasMore === false;
    button.textContent = cache.busy ? '正在加载历史…' : cache.hasMore === false ? '已到已保存的最早K线' : '加载更早K线';
    label.textContent = cache.error || cache.message;
    label.classList.toggle('negative', Boolean(cache.error));
  }

  async function loadChartHistory(around = null) {
    const cache = state.history, taskId = state.taskId;
    if (!cache || cache.taskId !== taskId || state.view !== 'task') return false;
    if (cache.busy) {
      await cache.promise;
      if (state.history !== cache || state.taskId !== taskId || state.view !== 'task') return false;
      if (around !== null && !cache.candles.has(Number(around))) return loadChartHistory(around);
      return true;
    }
    if (around === null && (!cache.candles.size || cache.hasMore === false)) return false;
    const earliest = cache.candles.size ? Math.min(...cache.candles.keys()) : null;
    const query = new URLSearchParams({limit: '500', ...(around !== null ? {around: String(Math.floor(around))} : {before: String(earliest)})});
    cache.busy = true; cache.error = ''; updateHistoryControls();
    cache.promise = (async () => {
      try {
        const payload = await api(`/api/tasks/${encodeURIComponent(taskId)}/chart?${query}`);
        if (state.history !== cache || state.taskId !== taskId || state.view !== 'task') return false;
        const previousCount = cache.candles.size;
        mergeChartHistory(payload, cache);
        if (around === null || (payload.candles?.[0]?.time < earliest)) cache.hasMore = Boolean(payload.has_more);
        const added = cache.candles.size - previousCount;
        cache.message = added ? `已加载 ${added} 根已保存K线；可继续拖动查看。` : around !== null ? '已定位该交易附近的已保存行情。' : '已到该任务已保存的最早K线。';
        updateCharts(state.detail);
        return true;
      } catch (error) {
        if (state.history === cache && state.taskId === taskId && state.view === 'task') { cache.error = `历史行情加载失败：${error.message}`; notify(cache.error, true); }
        return false;
      } finally {
        cache.busy = false;
        if (state.history === cache && state.taskId === taskId && state.view === 'task') updateHistoryControls();
      }
    })();
    return cache.promise;
  }

  function updateCharts(data) {
    const context = state.charts; if (!context) return;
    context.updating = true;
    try {
      const priceFormat = chartPriceFormat(data), priceFormatKey = JSON.stringify(priceFormat);
      if (context.priceFormatKey !== priceFormatKey) {
        context.candles.applyOptions({priceFormat});
        for (const line of context.lines.values()) if (line.pane === 'main') line.series.applyOptions({priceFormat});
        context.priceFormatKey = priceFormatKey;
      }
      if (!state.history || state.history.taskId !== data.task.id) state.history = newHistory(data.task.id);
      const cached = mergeChartHistory(data.chart, state.history, true, data.metadata?.indicator_preview);
      context.indicators = cached.indicators;
      const points = cached.candles, previousFirstTime = context.candleData[0]?.time;
      const previousRange = previousFirstTime !== undefined ? context.chart.timeScale().getVisibleRange() : null;
      context.candleData = points; context.candles.setData(points);
      context.volume.setData(points.map(point => ({time: point.time, value: Number(point.volume) || 0, color: point.close >= point.open ? '#12ad8b33' : '#e25e7033'})));
      document.getElementById('chart-empty').hidden = points.length > 0;
      if (!points.length) document.getElementById('chart-empty').innerHTML = `<strong>${data.task.status === 'draft' ? '草稿尚未启动' : '等待真实行情'}</strong><span>${data.task.status === 'draft' ? '启动后显示真实预热K线与实时行情。' : esc(data.task.connection?.message || '行情到达后自动更新，不显示合成数据。')}</span>`;
      const alive = new Set();
      for (const indicator of cached.indicators) {
        alive.add(indicator.id); const pane = indicator.pane === 'rsi' ? 'rsi' : 'main';
        let line = context.lines.get(indicator.id);
        if (!line) {
          const target = pane === 'rsi' ? context.rsiChart : context.chart;
          const series = target.addLineSeries({priceFormat: pane === 'rsi' ? {type: 'price', precision: 2, minMove: 0.01} : priceFormat, color: indicatorColor(indicator), lineWidth: 2, title: indicator.name || indicator.id, priceLineVisible: false, lastValueVisible: false});
          line = {series, pane, target, data: []}; context.lines.set(indicator.id, line);
          if (pane === 'rsi') for (const level of [30, 50, 70]) series.createPriceLine({price: level, color: chartTheme().grid, lineWidth: 1, lineStyle: 2, axisLabelVisible: true, title: ''});
        }
        line.data = cleanPoints(indicator.data);
        const values = new Map(line.data.map(point => [point.time, point.value]));
        line.series.setData(pane === 'rsi' ? points.map(point => values.has(point.time) ? {time: point.time, value: values.get(point.time)} : {time: point.time}) : line.data);
      }
      for (const [id, line] of context.lines) if (!alive.has(id)) { line.target.removeSeries(line.series); context.lines.delete(id); }
      const showRsi = state.showRsi && [...context.lines.values()].some(line => line.pane === 'rsi');
      if (!showRsi && context.hoverPane === 'rsi') { context.hoverTime = null; context.hoverPane = null; }
      document.getElementById('rsi-wrap').hidden = !showRsi;
      context.chart.applyOptions({timeScale: {visible: !showRsi}});
      const markers = [];
      const pointTimes = new Set(points.map(point => point.time));
      for (const trade of allChartTrades(data)) {
        const entry = candleTime(trade.entry_time_ms, data.task.interval);
        const exit = candleTime(trade.exit_time_ms, data.task.interval);
        const signal = candleTime(Number(trade.signal_time_ms) - 1, data.task.interval);
        if (pointTimes.has(signal)) markers.push({time: signal, position: trade.side === 'long' ? 'belowBar' : 'aboveBar', color: '#728bea', shape: 'square', text: '信号'});
        if (pointTimes.has(entry)) markers.push({time: entry, position: trade.side === 'long' ? 'belowBar' : 'aboveBar', color: trade.side === 'long' ? '#12ad8b' : '#e25e70', shape: trade.side === 'long' ? 'arrowUp' : 'arrowDown', text: `成交${trade.side === 'long' ? '多' : '空'}`});
        if (trade.exit_time_ms && pointTimes.has(exit)) markers.push({time: exit, position: trade.side === 'long' ? 'aboveBar' : 'belowBar', color: '#b38ce6', shape: 'circle', text: '平'});
      }
      context.candles.setMarkers(state.showPositions ? markers.sort((a, b) => a.time - b.time) : []);
      if (context.firstData && points.length) { context.chart.timeScale().fitContent(); context.firstData = false; }
      else if (previousRange && previousFirstTime !== points[0]?.time) context.chart.timeScale().setVisibleRange(previousRange);
      updateHistoryControls();
      scheduleOverlay();
    } finally { context.updating = false; renderChartLegend(context); }
  }

  function intervalSeconds(interval) { const match = /^(\d+)([mhdw])$/.exec(interval || ''); return match ? Number(match[1]) * ({m: 60, h: 3600, d: 86400, w: 604800}[match[2]]) : 14400; }
  function candleTime(ms, interval) { return finite(ms) && Number(ms) > 0 ? Math.floor(Number(ms) / 1000 / intervalSeconds(interval)) * intervalSeconds(interval) : null; }
  function allChartTrades(data) { const trades = [...(data.trades || [])]; if (data.position && !trades.some(trade => trade.id === data.position.id)) trades.push(data.position); return trades; }
  function stopTime(item, fallback) {
    const value = item.effective_from_ms ?? item.time_ms ?? item.updated_at_ms ?? item.effective_from ?? item.updated_at;
    return finite(value) ? Number(value) < 100000000000 ? Number(value) * 1000 : Number(value) : fallback;
  }
  let overlayFrame;
  function scheduleOverlay() { cancelAnimationFrame(overlayFrame); overlayFrame = requestAnimationFrame(drawOverlay); }

  function drawOverlay() {
    const context = state.charts, data = state.detail, svg = document.getElementById('trade-overlay');
    if (!context || !data || !svg) return;
    context.hitBoxes = [];
    if (!state.showPositions || !context.candleData.length) { svg.innerHTML = ''; return; }
    const width = document.getElementById('price-wrap').clientWidth, height = document.getElementById('price-wrap').clientHeight;
    const rightWidth = Number(context.chart.priceScale('right').width()) || 0;
    const leftWidth = context.chart.options().leftPriceScale.visible ? Number(context.chart.priceScale('left').width()) || 0 : 0;
    const plotWidth = Math.max(1, width - rightWidth - leftWidth), plotHeight = height - (document.getElementById('rsi-wrap').hidden ? 25 : 0);
    svg.setAttribute('viewBox', `0 0 ${width} ${height}`);
    const interval = intervalSeconds(data.task.interval);
    const timeX = ms => {
      if (!finite(ms)) return null;
      const aligned = candleTime(ms, data.task.interval);
      const coordinate = context.chart.timeScale().timeToCoordinate(aligned);
      if (coordinate !== null) return coordinate;
      const times = context.candleData;
      let lower = 0, upper = times.length;
      while (lower < upper) { const middle = (lower + upper) >> 1; if (times[middle].time < aligned) lower = middle + 1; else upper = middle; }
      let index;
      if (lower === 0) index = (aligned - times[0].time) / interval;
      else if (lower === times.length) index = times.length - 1 + (aligned - times[times.length - 1].time) / interval;
      else index = lower - 1 + (aligned - times[lower - 1].time) / (times[lower].time - times[lower - 1].time);
      return context.chart.timeScale().logicalToCoordinate(index);
    };
    const yPrice = value => finite(value) ? context.candles.priceToCoordinate(Number(value)) : null;
    let markup = `<defs><clipPath id="trade-plot-clip"><rect width="${plotWidth}" height="${plotHeight}"/></clipPath></defs><g clip-path="url(#trade-plot-clip)">`;
    for (const trade of allChartTrades(data)) {
      let x1 = timeX(trade.entry_time_ms), x2 = timeX(trade.exit_time_ms || data.task.last_quote_time_ms || (context.candleData[context.candleData.length - 1].time + interval) * 1000);
      const entry = yPrice(trade.entry_fill), stop = yPrice(trade.initial_stop), target = yPrice(trade.target ?? trade.activation_level);
      if ([x1, x2, entry].some(value => value === null || !Number.isFinite(value))) continue;
      if (x2 < 0 || x1 > plotWidth) continue;
      x2 = Math.max(x2, x1 + 12);
      context.hitBoxes.push({id: trade.id, x1, x2, y1: Math.min(entry, stop ?? entry, target ?? entry) - 4, y2: Math.max(entry, stop ?? entry, target ?? entry) + 4});
      const selected = state.selectedTrade === trade.id, opacity = selected ? 0.19 : 0.08;
      markup += `<g data-trade-id="${esc(trade.id)}"><title>#${esc(shortId(trade.id))} ${trade.side === 'long' ? '多单' : '空单'} · 开仓 ${price(trade.entry_fill)} · ${trade.exit_time_ms ? '已平仓' : '持仓中'}</title>`;
      if (target !== null) markup += `<rect x="${x1}" y="${Math.min(entry, target)}" width="${x2 - x1}" height="${Math.max(1, Math.abs(entry - target))}" fill="#12ad8b" fill-opacity="${opacity}"/>`;
      if (stop !== null) markup += `<rect x="${x1}" y="${Math.min(entry, stop)}" width="${x2 - x1}" height="${Math.max(1, Math.abs(entry - stop))}" fill="#e25e70" fill-opacity="${opacity}"/>`;
      markup += `<line x1="${x1}" y1="${entry}" x2="${x2}" y2="${entry}" stroke="${selected ? '#849cff' : '#8292b1'}" stroke-width="${selected ? 1.5 : 1}"/>`;
      if (stop !== null) markup += `<line x1="${x1}" y1="${stop}" x2="${x2}" y2="${stop}" stroke="#e25e70" stroke-dasharray="4 3" opacity=".65"/>`;
      if (target !== null) markup += `<line x1="${x1}" y1="${target}" x2="${x2}" y2="${target}" stroke="#12ad8b" stroke-dasharray="4 3" opacity=".7"/>`;
      const history = [...(trade.stop_history || [])].sort((a, b) => stopTime(a, trade.entry_time_ms) - stopTime(b, trade.entry_time_ms));
      let previousX = x1, previousY = stop, stepPath = previousY === null ? '' : `M ${x1} ${previousY}`;
      for (const item of history) {
        const nextX = timeX(stopTime(item, trade.entry_time_ms)), nextY = yPrice(item.stop);
        if (nextX === null || nextY === null || nextX < x1 || nextX > x2) continue;
        if (!stepPath) stepPath = `M ${nextX} ${nextY}`; else stepPath += ` H ${nextX} V ${nextY}`;
        previousX = nextX; previousY = nextY;
      }
      if (stepPath && previousY !== null && previousX <= x2) markup += `<path d="${stepPath} H ${x2}" fill="none" stroke="#e25e70" stroke-width="${selected ? 1.8 : 1.2}" opacity=".9"/>`;
      if (selected) markup += `<text x="${Math.max(4, x1 + 5)}" y="${Math.max(13, Math.min(plotHeight - 5, Math.min(entry, target ?? entry, stop ?? entry) - 7))}">#${esc(shortId(trade.id))} ${trade.side === 'long' ? '多头仓位' : '空头仓位'}${trade.target == null ? ' · 激活位' : ''}</text>`;
      markup += '</g>';
    }
    svg.innerHTML = `${markup}</g>`;
  }

  async function focusTrade(id = state.selectedTrade) {
    const data = state.detail; if (!state.charts || !data) return;
    const trade = allChartTrades(data).find(item => item.id === id); if (!trade) return;
    const request = ++state.focusRequest, taskId = data.task.id;
    state.selectedTrade = id; state.tab = 'trades'; renderTab();
    const step = intervalSeconds(data.task.interval), entry = candleTime(trade.entry_time_ms, data.task.interval), exit = candleTime(trade.exit_time_ms || data.task.last_quote_time_ms, data.task.interval) || entry + 5 * step;
    if (!state.history?.candles.has(entry)) await loadChartHistory(entry);
    if (request !== state.focusRequest || state.taskId !== taskId || state.view !== 'task' || state.selectedTrade !== id || !state.charts) return;
    const context = state.charts;
    if (!context.candleData.some(point => point.time === entry)) { notify('该交易附近的已保存K线暂不可用，请查看历史行情状态。', true); return; }
    context.candles.applyOptions({autoscaleInfoProvider: selectedTradeAutoscale});
    context.chart.priceScale('right').applyOptions({autoScale: true});
    context.chart.timeScale().setVisibleRange({from: entry - step * 9, to: Math.max(entry + step * 9, exit + step * 7)});
    scheduleOverlay();
  }

  function drawEquity() {
    const context = state.charts, container = document.getElementById('equity-chart'); if (!context || !container || !window.LightweightCharts) return;
    if (context.equityContainer !== container) {
      context.equityChart?.remove(); context.equityContainer = container; context.equityFirstData = true;
      context.equityChart = LightweightCharts.createChart(container, chartOptions(container, 190));
      context.equitySeries = context.equityChart.addAreaSeries({lineColor: '#718feb', topColor: '#718feb33', bottomColor: '#718feb00', lineWidth: 2, priceLineVisible: false});
    }
    const points = cleanPoints((state.detail.equity || []).map(point => ({time: point.time, value: point.equity})));
    context.equitySeries.setData(points);
    if (context.equityFirstData && points.length) { context.equityChart.timeScale().fitContent(); context.equityFirstData = false; }
  }

  async function taskAction(action) {
    if (state.actionBusy || !state.detail) return;
    const task = state.detail.task, id = task.id;
    if (action === 'stop' && !window.confirm('结束任务将停止开新仓。已有持仓继续执行退出规则，平仓后停止行情订阅。确认结束？')) return;
    if (action === 'close' && !window.confirm('将请求在下一笔有效实时报价平仓，并结束任务。最终成交价格由当时报价决定。确认？')) return;
    state.actionBusy = true; updateTaskView();
    try {
      await api(`/api/tasks/${encodeURIComponent(id)}/action`, {method: 'POST', body: JSON.stringify({action})});
      if (state.taskId === id && state.view === 'task') await loadTask(true);
      await refreshTaskList();
      notify({start: '已提交启动，请查看行情状态。', pause: '已暂停开新仓；现有持仓继续按规则管理。', resume: '已恢复开新仓。', stop: '已提交结束任务；已有持仓按退出规则处理。', close: '已请求下一笔有效报价平仓并结束。'}[action] || '操作已提交。');
    } catch (error) { notify(error.message, true); }
    finally { state.actionBusy = false; if (state.view === 'task' && state.detail && state.taskId === id) updateTaskView(); }
  }

  async function deleteTask() {
    if (state.actionBusy || !canDeleteTask(state.detail)) return;
    const task = state.detail.task, id = task.id;
    if (!window.confirm(`删除任务“${task.name}”？\n\n将永久删除此任务及其交易、账户、K线与日志。其他任务和策略库不会受到影响。\n\n建议先在“交易明细”导出CSV保存记录。确认删除？`)) return;
    state.actionBusy = true; state.deletingTaskId = id;
    state.taskRequest++; state.taskBusy = false;
    updateTaskView();
    let deleted = false;
    try {
      const result = await api(`/api/tasks/${encodeURIComponent(id)}`, {method: 'DELETE'});
      if (result.deleted !== true) throw new Error('后台未确认删除，请刷新后核对任务状态。');
      deleted = true; state.deletedTaskIds.add(id);
      state.tasks = state.tasks.filter(item => item.id !== id);
      if (state.bootstrap) state.bootstrap.tasks = (state.bootstrap.tasks || []).filter(item => item.id !== id);
      if (state.taskId === id) {
        const nextId = state.tasks[0]?.id || null, showNext = state.view === 'task';
        state.taskRequest++; state.taskBusy = false; state.focusRequest++;
        state.detail = null; state.history = null; state.selectedTrade = null; state.taskError = '';
        state.tab = 'trades'; state.tabSignature = null; state.tabUi.clear(); state.shellTaskId = null;
        destroyCharts(); state.taskId = null; rememberTask();
        if (showNext && nextId) openTask(nextId);
        else { state.taskId = nextId; rememberTask(); if (showNext) renderEmpty(); }
      }
      renderSidebar(); notify(`已删除任务“${task.name}”，其他任务和策略库保持不变。`);
    } catch (error) { notify(`删除失败：${error.message}`, true); }
    finally {
      state.actionBusy = false; state.deletingTaskId = null;
      if (state.view === 'task' && state.detail?.task.id === state.taskId) updateTaskView();
      if (!deleted && state.view === 'task' && state.taskId === id) loadTask(true);
    }
  }

  document.addEventListener('click', event => {
    const button = event.target.closest('button,[data-trade-id]'); if (!button || button.disabled) return;
    if (button.dataset.taskId) { openTask(button.dataset.taskId); return; }
    if (button.dataset.tab) { state.tab = button.dataset.tab; renderTab(); return; }
    if (button.dataset.tradeId) { focusTrade(button.dataset.tradeId); return; }
    if (button.dataset.useStrategy) { beginWizard({strategyId: button.dataset.useStrategy}); return; }
    if (button.dataset.editStrategy) { beginEditor(button.dataset.editStrategy); return; }
    if (button.dataset.inspectStrategy) {
      const node = document.getElementById(`strategy-detail-${button.dataset.inspectStrategy}`), strategy = strategyById(button.dataset.inspectStrategy);
      if (node && strategy) { node.hidden = !node.hidden; if (!node.hidden) node.innerHTML = jsonBlock(strategy.definition || strategy); }
      return;
    }
    if (button.dataset.wizardStrategy) { const wizard = state.wizard; wizard.strategyId = button.dataset.wizardStrategy; wizard.strategySnapshot = null; wizard.error = ''; renderWizard(); return; }
    if (button.dataset.addCondition) { state.editor.definition[button.dataset.addCondition].conditions.push({left: 'close', op: 'gt', right: state.editor.definition.indicators[0]?.id || 0}); renderEditor(); return; }
    if (button.dataset.removeCondition) { const [key, index] = button.dataset.removeCondition.split(':'); state.editor.definition[key].conditions.splice(Number(index), 1); renderEditor(); return; }
    if (button.dataset.removeIndicator !== undefined) {
      const definition = state.editor.definition, index = Number(button.dataset.removeIndicator), indicator = definition.indicators[index];
      const used = ['long', 'short', 'long_exit', 'short_exit'].some(key => definition[key].conditions.some(condition => condition.left === indicator.id || condition.right === indicator.id)) || (definition.exit.stop_type === 'indicator' && definition.exit.stop_indicator === indicator.id);
      if (used) { notify('该指标仍被交易条件或止损引用，请先调整引用。', true); return; }
      definition.indicators.splice(index, 1); renderEditor(); return;
    }
    const action = button.dataset.action;
    if (action === 'delete-task') { deleteTask(); return; }
    if (action?.startsWith('task-')) { taskAction(action.slice(5)); return; }
    switch (action) {
      case 'theme': {
        const dark = chartTheme().dark; document.documentElement.dataset.theme = dark ? 'light' : 'dark';
        if (state.view === 'task' && state.detail) { const range = state.charts?.chart.timeScale().getVisibleLogicalRange(); taskShell(); updateTaskView(); if (range && state.charts) state.charts.chart.timeScale().setVisibleLogicalRange(range); }
        break;
      }
      case 'refresh': bootstrap(!state.bootstrap).then(ok => { if (ok && state.view === 'task' && state.taskId) loadTask(true); }); break;
      case 'new-task': if (state.bootstrap) beginWizard(); else notify('请先连接后台。', true); break;
      case 'retry-task': loadTask(true); break;
      case 'library': renderLibrary(); break;
      case 'new-strategy': beginEditor(); break;
      case 'copy-task': if (state.detail) beginWizard({task: state.detail.task}); break;
      case 'edit-draft': if (state.detail) beginWizard({task: state.detail.task, edit: true}); break;
      case 'cancel-wizard': if (state.taskId) openTask(state.taskId); else renderLibrary(); break;
      case 'wizard-back': state.wizard.step = Math.max(0, state.wizard.step - 1); state.wizard.error = ''; renderWizard(); break;
      case 'wizard-next': { const error = validateWizard(); if (error) state.wizard.error = error; else { state.wizard.error = ''; state.wizard.step++; } renderWizard(); break; }
      case 'save-draft': saveTask(false); break;
      case 'start-new': saveTask(true); break;
      case 'save-strategy': saveStrategy(); break;
      case 'add-indicator': { if (state.editor.definition.indicators.length >= 20) { notify('首版最多添加20个指标。', true); break; } let index = 1; while (state.editor.definition.indicators.some(item => item.id === `indicator_${index}`)) index++; state.editor.definition.indicators.push({id: `indicator_${index}`, type: 'EMA', length: 20, source: 'close'}); renderEditor(); break; }
      case 'chart-latest': state.charts?.chart.timeScale().scrollToRealTime(); scheduleOverlay(); break;
      case 'chart-history': loadChartHistory(); break;
      case 'focus-trade': focusTrade(); break;
    }
  });

  function formInput(event, isChange = false) {
    const element = event.target;
    if (element.id === 'task-search') { state.search = element.value; renderSidebar(); return; }
    if (element.hasAttribute('data-wizard')) {
      const key = element.dataset.wizard;
      if (key.startsWith('account.')) { const field = key.slice(8); state.wizard.account[field] = field === 'sizing' ? element.value : element.value === '' ? '' : Number(element.value); }
      else state.wizard[key] = key === 'symbol' ? element.value.trim().toUpperCase() : element.value;
      const preview = document.getElementById('sizing-preview'); if (preview) preview.textContent = sizingPreview(state.wizard.account);
      if (isChange && key === 'account.sizing') renderWizard();
    }
    if (element.hasAttribute('data-wizard-param')) state.wizard.params[element.dataset.wizardParam] = element.dataset.wizardParam === 'prior_bars' ? Number(element.value) : element.value;
    if (element.hasAttribute('data-editor-name')) state.editor.name = element.value;
    if (element.hasAttribute('data-indicator-index')) {
      const indicator = state.editor.definition.indicators[Number(element.dataset.indicatorIndex)], field = element.dataset.indicatorField;
      indicator[field] = field === 'length' ? Number(element.value) : element.value;
      if (isChange) renderEditor(); else updateRulePreview();
    }
    if (element.hasAttribute('data-group-enabled')) { state.editor.definition[element.dataset.groupEnabled].enabled = element.checked; if (isChange) renderEditor(); }
    if (element.hasAttribute('data-group-logic')) { state.editor.definition[element.dataset.groupLogic].logic = element.value; updateRulePreview(); }
    if (element.hasAttribute('data-exit-field')) {
      const field = element.dataset.exitField; state.editor.definition.exit[field] = ['stop_percent', 'reward_risk'].includes(field) ? element.value === '' ? '' : Number(element.value) : element.value;
      if (field === 'stop_type' && element.value === 'indicator' && !state.editor.definition.indicators.some(item => item.id === state.editor.definition.exit.stop_indicator && item.type !== 'RSI')) state.editor.definition.exit.stop_indicator = state.editor.definition.indicators.find(item => item.type !== 'RSI')?.id || '';
      if (isChange && field === 'stop_type') renderEditor();
    }
    if (element.hasAttribute('data-condition-group')) {
      const condition = state.editor.definition[element.dataset.conditionGroup].conditions[Number(element.dataset.conditionIndex)], field = element.dataset.conditionField;
      if (field === 'right_source') {
        condition.right = element.value === '__number' ? 50 : element.value;
        if (isChange) renderEditor();
      } else if (field === 'op') {
        condition.op = element.value;
        if (!condition.left) condition.left = 'close';
        if (condition.right === undefined) condition.right = state.editor.definition.indicators[0]?.id || 0;
        if (element.value === 'between') { condition.right = typeof condition.right === 'number' ? condition.right : 30; condition.upper = 70; condition.include_lower = true; condition.include_upper = true; }
        if (element.value === 'wick_above' || element.value === 'wick_below') condition.left = element.value === 'wick_above' ? 'low' : 'high';
        if (isChange) renderEditor();
      } else { condition[field] = field.startsWith('include_') ? element.checked : field === 'right' || field === 'upper' ? element.value === '' ? '' : Number(element.value) : element.value; updateRulePreview(); }
    }
    if (isChange && element.hasAttribute('data-trade-filter')) { state.tradeFilter = element.value; renderTab(); }
    if (isChange && element.dataset.toggle) {
      if (element.dataset.toggle === 'rsi') state.showRsi = element.checked; else state.showPositions = element.checked;
      if (state.detail) updateCharts(state.detail);
    }
  }

  document.addEventListener('input', event => formInput(event));
  document.addEventListener('change', event => formInput(event, true));
  document.addEventListener('keydown', event => { const row = event.target.closest('.trade-row'); if (row && ['Enter', ' '].includes(event.key)) { event.preventDefault(); focusTrade(row.dataset.tradeId); } });
  document.addEventListener('visibilitychange', () => { if (!document.hidden) { loadTask(true); refreshTaskList(); } });
  window.addEventListener('resize', () => { const container = document.getElementById('equity-chart'); if (container && state.charts?.equityChart) state.charts.equityChart.resize(container.clientWidth, 190); scheduleOverlay(); });

  let lastTaskPoll = 0, lastListPoll = 0;
  setInterval(() => {
    const now = Date.now(), slow = document.hidden;
    if (now - lastTaskPoll >= (slow ? 10000 : 1000)) { lastTaskPoll = now; loadTask(); }
    if (state.bootstrap && now - lastListPoll >= (slow ? 15000 : 3000)) { lastListPoll = now; refreshTaskList(); }
  }, 1000);
  bootstrap(true);
})();
