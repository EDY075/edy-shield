/* ============================================================
   EDY SHIELD — UI (Sprint 3, Missão 9)
   ------------------------------------------------------------
   Camada de APRESENTAÇÃO apenas. Toda a lógica de negócio vive
   nos plugins/serviços do backend; este arquivo apenas:
     1. faz fetch para a API REST (app/ui/server.py);
     2. renderiza os resultados no DOM.
   ============================================================ */
(function () {
  'use strict';

  /* ------------------------------------------------------------
     Helpers
     ------------------------------------------------------------ */
  function el(id) { return document.getElementById(id); }

  function esc(value) {
    var div = document.createElement('div');
    div.textContent = String(value == null ? '' : value);
    return div.innerHTML;
  }

  async function api(url, options) {
    var res = await fetch(url, options);
    var data = await res.json().catch(function () { return {}; });
    if (!res.ok) {
      throw new Error(data.error || ('Erro HTTP ' + res.status));
    }
    return data;
  }

  function setStatus(ok, label) {
    var pill = el('api-status');
    if (!pill) return;
    pill.classList.toggle('status-pill--online', ok);
    pill.querySelector('.status-pill__dot').style.background = ok ? '' : '#ff4d4d';
    pill.lastChild.textContent = label;
  }

  /* ------------------------------------------------------------
     Navegação entre views (SPA leve)
     ------------------------------------------------------------ */
  var VIEW_TITLES = {
    'dashboard': 'Painel de Operações',
    'hash-checker': 'Hash Checker',
    'log-analyzer': 'Log Analyzer',
    'fim': 'File Integrity Monitor',
    'history': 'Histórico',
    'reports': 'Relatórios',
    'modules': 'Módulos'
  };

  function showView(name) {
    document.querySelectorAll('.view').forEach(function (v) {
      v.classList.toggle('is-active', v.id === 'view-' + name);
    });
    document.querySelectorAll('.nav-item').forEach(function (a) {
      var active = a.getAttribute('data-view') === name;
      a.classList.toggle('nav-item--active', active);
      if (active) a.setAttribute('aria-current', 'true');
      else a.removeAttribute('aria-current');
    });
    el('view-title').textContent = VIEW_TITLES[name] || 'Painel de Operações';
    document.querySelector('.content').scrollTop = 0;
    window.scrollTo(0, 0);

    // Deep-linking: mantém a view atual na URL (#fim, #hash-checker, ...)
    if (history.replaceState && window.location.hash !== '#' + name) {
      history.replaceState(null, '', '#' + name);
    }

    // Carregar dados sob demanda
    if (name === 'dashboard') loadDashboard();
    if (name === 'history') loadHistory();
    if (name === 'reports') loadReports();
    if (name === 'modules') loadModules();
    if (name === 'fim') loadFimBaselines();
  }

  /* ------------------------------------------------------------
     Dashboard
     ------------------------------------------------------------ */
  async function loadDashboard() {
    try {
      var plugins = await api('/api/plugins');
      var history = await api('/api/history');
      el('stat-plugins').textContent = String((plugins.plugins || []).length);
      el('stat-scans').textContent = String((history.entries || []).length);
      el('stat-status').textContent = 'Online';
      el('engine-version').textContent = 'v' + (plugins.version || '2.0.0');
      el('footer-version').textContent = 'v' + (plugins.version || '2.0.0');
      setStatus(true, 'SYSTEM ONLINE');
      renderModuleGrid(el('dashboard-modules'), plugins.plugins || []);
    } catch (err) {
      setStatus(false, 'API OFFLINE');
      el('stat-status').textContent = 'Offline';
    }
  }

  function renderModuleGrid(container, plugins) {
    container.innerHTML = '';
    if (!plugins.length) {
      container.innerHTML = '<p class="hash-result__note">Nenhum plugin registrado.</p>';
      return;
    }
    plugins.forEach(function (plugin) {
      var view = plugin.name === 'hash_checker' ? 'hash-checker'
        : plugin.name === 'log_analyzer' ? 'log-analyzer'
        : plugin.name === 'file_integrity' ? 'fim' : null;
      var card = document.createElement('article');
      card.className = 'module-card module-card--active';
      var badge = plugin.name === 'hash_checker'
        ? '<span class="module-card__state module-card__state--active">Ativo</span>'
        : '<span class="module-card__state module-card__state--active">Ativo</span>';
      card.innerHTML =
        '<div class="module-card__top">' +
        '<span class="module-card__icon module-card__icon--active" aria-hidden="true">' +
        '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
        'stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="4" width="16" height="16" rx="2"/>' +
        '<path d="M8 9h8M8 13h5M8 17h3"/></svg></span>' + badge + '</div>' +
        '<h3 class="module-card__title">' + esc(plugin.description.split('.')[0]) + '</h3>' +
        '<p class="module-card__desc">' + esc(plugin.description) + '</p>' +
        '<div class="module-card__meta">' +
        '<span class="module-card__meta-item">v' + esc(plugin.version) + '</span>' +
        '<span class="module-card__meta-item">' + esc(plugin.author) + '</span></div>';
      if (view) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'module-card__action';
        btn.textContent = 'Abrir módulo';
        btn.addEventListener('click', function () { showView(view); });
        card.appendChild(btn);
      }
      container.appendChild(card);
    });
  }

  /* ------------------------------------------------------------
     Hash Checker
     ------------------------------------------------------------ */
  async function runHashScan() {
    var target = el('hash-input').value.trim();
    var expected = el('hash-expected').value.trim();
    if (!target) { renderHashError('Informe um texto ou caminho de arquivo.'); return; }
    var options = { algorithm: el('hash-algo').value };
    if (expected) options.expected = expected;

    var resultBox = el('hash-result');
    resultBox.innerHTML = '<p class="hash-result__note">Executando...</p>';
    try {
      var data = await api('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plugin: 'hash_checker', target: target, options: options })
      });
      renderScanResult(resultBox, data.result);
    } catch (err) {
      renderHashError(err.message);
    }
  }

  function renderHashError(message) {
    el('hash-result').innerHTML =
      '<p class="hash-result__note" style="color: var(--accent-red);">' + esc(message) + '</p>';
  }

  /* ------------------------------------------------------------
     Log Analyzer
     ------------------------------------------------------------ */
  async function runLogScan() {
    var target = el('log-path').value.trim();
    if (!target) { renderLogError('Informe o caminho do arquivo de log.'); return; }
    var maxLines = parseInt(el('log-max-lines').value, 10) || 0;
    var options = {};
    if (maxLines > 0) options.max_lines = maxLines;

    var resultBox = el('log-result');
    resultBox.innerHTML = '<p class="hash-result__note">Executando...</p>';
    try {
      var data = await api('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plugin: 'log_analyzer', target: target, options: options })
      });
      renderScanResult(resultBox, data.result);
    } catch (err) {
      renderLogError(err.message);
    }
  }

  function renderLogError(message) {
    el('log-result').innerHTML =
      '<p class="hash-result__note" style="color: var(--accent-red);">' + esc(message) + '</p>';
  }

  /* ------------------------------------------------------------
     Renderização genérica de ScanResult
     ------------------------------------------------------------ */
  function renderScanResult(container, result) {
    if (!result) { container.innerHTML = '<p class="hash-result__note">Sem resultado.</p>'; return; }
    var severityColor = {
      INFO: 'var(--accent-cyan)', LOW: 'var(--accent-gold)',
      MEDIUM: '#f0883e', HIGH: 'var(--accent-red)', CRITICAL: '#ff2d55'
    }[result.max_severity] || 'var(--text-secondary)';

    var html =
      '<div class="hash-result__head">' +
      '<span class="hash-result__label">' + esc(result.plugin_name) + ' v' + esc(result.plugin_version) + '</span>' +
      '<span class="hash-result__status"><span class="hash-result__ok" style="background:' + severityColor + '"></span>' +
      esc(result.max_severity) + '</span></div>' +
      '<p class="hash-result__note">' + esc(result.summary) + '</p>' +
      '<p class="hash-result__note">Timestamp: <code>' + esc(result.timestamp) + '</code></p>';

    if (result.stats && Object.keys(result.stats).length) {
      html += '<p class="hash-result__note"><strong>Estatísticas:</strong> ';
      var parts = Object.keys(result.stats).map(function (k) {
        return esc(k) + '=' + esc(result.stats[k]);
      });
      html += parts.join(' · ') + '</p>';
    }

    if (result.findings && result.findings.length) {
      html += '<ul class="finding-list">';
      result.findings.forEach(function (f) {
        var c = {
          INFO: 'var(--accent-cyan)', LOW: 'var(--accent-gold)',
          MEDIUM: '#f0883e', HIGH: 'var(--accent-red)', CRITICAL: '#ff2d55'
        }[f.severity] || 'var(--text-secondary)';
        html += '<li><span class="finding-sev" style="color:' + c + '">' + esc(f.severity) + '</span>' +
          (f.source ? '<code class="finding-src">' + esc(f.source) + '</code> ' : '') +
          esc(f.message) + '</li>';
      });
      html += '</ul>';
    }

    if (result.observations && result.observations.length) {
      html += '<p class="hash-result__note"><strong>Observações:</strong></p><ul class="finding-list">';
      result.observations.forEach(function (o) { html += '<li>' + esc(o) + '</li>'; });
      html += '</ul>';
    }

    container.innerHTML = html;
  }

  /* ------------------------------------------------------------
     File Integrity Monitor
     ------------------------------------------------------------ */
  async function loadFimBaselines() {
    var select = el('fim-baseline');
    if (!select) return;
    try {
      var data = await api('/api/fim/baselines');
      var baselines = data.baselines || [];
      select.innerHTML = '<option value="">-- selecionar baseline --</option>';
      baselines.forEach(function (b) {
        var opt = document.createElement('option');
        opt.value = b.id;
        opt.textContent = b.id + ' · ' + b.entries + ' entradas · ' + b.algorithm;
        select.appendChild(opt);
      });
      el('fim-result').innerHTML =
        '<p class="hash-result__note">' + baselines.length + ' baseline(s) disponível(eis).</p>';
    } catch (err) {
      el('fim-result').innerHTML =
        '<p class="hash-result__note" style="color: var(--accent-red);">' + esc(err.message) + '</p>';
    }
  }

  function toggleFimAction() {
    var action = el('fim-action').value;
    var baselineGroup = el('fim-baseline-group');
    var btn = el('fim-execute');
    if (action === 'scan') {
      baselineGroup.style.display = '';
      btn.textContent = 'Executar Scan';
    } else {
      baselineGroup.style.display = 'none';
      btn.textContent = 'Criar Baseline';
    }
  }

  async function runFim() {
    var target = el('fim-path').value.trim();
    if (!target) { renderFimError('Informe o caminho do diretório.'); return; }

    var action = el('fim-action').value;
    var options = { action: action, algorithm: el('fim-algo').value, recursive: true };
    if (action === 'scan') {
      var baselineId = el('fim-baseline').value;
      if (!baselineId) { renderFimError('Selecione uma baseline para o scan.'); return; }
      options.baseline_id = baselineId;
    }

    var resultBox = el('fim-result');
    resultBox.innerHTML = '<p class="hash-result__note">Executando...</p>';
    try {
      var data = await api('/api/scan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ plugin: 'file_integrity', target: target, options: options })
      });
      renderScanResult(resultBox, data.result);
      loadFimBaselines();
    } catch (err) {
      renderFimError(err.message);
    }
  }

  function renderFimError(message) {
    el('fim-result').innerHTML =
      '<p class="hash-result__note" style="color: var(--accent-red);">' + esc(message) + '</p>';
  }

  /* ------------------------------------------------------------
     Histórico
     ------------------------------------------------------------ */
  async function loadHistory() {
    var box = el('history-table');
    try {
      var data = await api('/api/history');
      var entries = data.entries || [];
      if (!entries.length) {
        box.innerHTML = '<p class="hash-result__note">Nenhuma varredura no histórico.</p>';
        return;
      }
      var html = '<table class="data-table"><thead><tr>' +
        '<th>ID</th><th>Plugin</th><th>Versão</th><th>Timestamp</th><th>Severidade</th></tr></thead><tbody>';
      entries.forEach(function (entry) {
        html += '<tr><td><code>' + esc(entry.id) + '</code></td>' +
          '<td>' + esc(entry.plugin_name) + '</td>' +
          '<td>' + esc(entry.plugin_version) + '</td>' +
          '<td>' + esc(entry.timestamp) + '</td>' +
          '<td>' + esc(entry.max_severity) + '</td></tr>';
      });
      html += '</tbody></table>';
      box.innerHTML = html;
    } catch (err) {
      box.innerHTML = '<p class="hash-result__note" style="color: var(--accent-red);">' + esc(err.message) + '</p>';
    }
  }

  /* ------------------------------------------------------------
     Relatórios
     ------------------------------------------------------------ */
  async function loadReports() {
    var box = el('reports-table');
    try {
      var data = await api('/api/history');
      var entries = data.entries || [];
      if (!entries.length) {
        box.innerHTML = '<p class="hash-result__note">Nenhuma varredura disponível para exportar.</p>';
        return;
      }
      var html = '<table class="data-table"><thead><tr>' +
        '<th>ID</th><th>Plugin</th><th>Severidade</th><th>Exportar</th></tr></thead><tbody>';
      entries.forEach(function (entry) {
        var id = encodeURIComponent(entry.id);
        html += '<tr><td><code>' + esc(entry.id) + '</code></td>' +
          '<td>' + esc(entry.plugin_name) + '</td>' +
          '<td>' + esc(entry.max_severity) + '</td>' +
          '<td class="report-links">' +
          '<a href="/api/report/' + id + '?fmt=json" download>JSON</a> · ' +
          '<a href="/api/report/' + id + '?fmt=txt" download>TXT</a> · ' +
          '<a href="/api/report/' + id + '?fmt=html" download>HTML</a> · ' +
          '<a href="/api/report/' + id + '?fmt=md" download>MD</a></td></tr>';
      });
      html += '</tbody></table>';
      box.innerHTML = html;
    } catch (err) {
      box.innerHTML = '<p class="hash-result__note" style="color: var(--accent-red);">' + esc(err.message) + '</p>';
    }
  }

  /* ------------------------------------------------------------
     Módulos (grid informativo)
     ------------------------------------------------------------ */
  async function loadModules() {
    try {
      var data = await api('/api/plugins');
      renderModuleGrid(el('modules-grid'), data.plugins || []);
    } catch (err) {
      el('modules-grid').innerHTML =
        '<p class="hash-result__note" style="color: var(--accent-red);">' + esc(err.message) + '</p>';
    }
  }

  /* ------------------------------------------------------------
     Init
     ------------------------------------------------------------ */
  function init() {
    // Menu mobile
    var sidebar = el('sidebar');
    var overlay = el('sidebar-overlay');
    var menuToggle = el('menu-toggle');
    function setMenu(open) {
      sidebar.classList.toggle('is-open', open);
      overlay.classList.toggle('is-visible', open);
      menuToggle.setAttribute('aria-expanded', String(open));
      document.body.classList.toggle('no-scroll', open);
    }
    menuToggle.addEventListener('click', function () { setMenu(!sidebar.classList.contains('is-open')); });
    overlay.addEventListener('click', function () { setMenu(false); });
    window.addEventListener('keydown', function (e) { if (e.key === 'Escape') setMenu(false); });

    // Navegação por data-view
    document.querySelectorAll('.nav-item[data-view]').forEach(function (a) {
      a.addEventListener('click', function (e) {
        e.preventDefault();
        showView(a.getAttribute('data-view'));
        setMenu(false);
      });
    });

    // Ações
    el('hash-calc').addEventListener('click', runHashScan);
    el('log-analyze').addEventListener('click', runLogScan);
    el('fim-execute').addEventListener('click', runFim);
    el('fim-action').addEventListener('change', toggleFimAction);
    el('dashboard-refresh').addEventListener('click', loadDashboard);
    el('history-refresh').addEventListener('click', loadHistory);
    el('reports-refresh').addEventListener('click', loadReports);

    // Relógio
    var clock = el('live-clock');
    function tick() {
      var now = new Date();
      var pad = function (n) { return String(n).padStart(2, '0'); };
      clock.textContent = now.toLocaleDateString('pt-BR') + ' · ' +
        pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds()) +
        ' UTC' + (now.getTimezoneOffset() <= 0 ? '+' : '-') + Math.abs(now.getTimezoneOffset() / 60);
    }
    tick();
    setInterval(tick, 1000);

    // View inicial: respeita o hash da URL (#fim, #hash-checker, ...)
    var initial = (window.location.hash || '').replace('#', '');
    showView(VIEW_TITLES[initial] ? initial : 'dashboard');
  }

  document.addEventListener('DOMContentLoaded', init);
})();
