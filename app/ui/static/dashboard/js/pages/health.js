/**
 * EDY Shield Dashboard — System Health Enterprise (M4.4.8)
 * Monitor de saúde com KPIs reais, status de serviços, lista de plugins,
 * badges, última atualização e mini gráficos.
 */

Router.register('health', {
  title: 'System Health',
  render: function () {
    return (
      '<div class="page-header page-header-compact">' +
      '  <div class="page-header-left">' +
      '    <h1>System Health</h1>' +
      '    <p>Monitor de sa\u00fade e performance</p>' +
      '  </div>' +
      '  <div style="display: flex; align-items: center; gap: 12px;">' +
      '    <span class="health-updated" id="healthUpdated">\u00daltima atualiza\u00e7\u00e3o: —</span>' +
      '    <button class="btn btn-sm btn-ghost" onclick="HealthPage.refresh()">&#10227; Atualizar</button>' +
      '  </div>' +
      '</div>' +
      '<div class="stat-grid" id="healthKpiGrid">' +
      Components.skeletonHTML('card', 4) +
      '</div>' +
      '<div class="content-grid">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Status dos Servi\u00e7os</span></div>' +
      '    <div class="card-body" id="healthComponentsBody">' +
      Components.skeletonHTML('bar', 5) +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alert Engine</span></div>' +
      '    <div class="card-body" id="healthEngineBody">' +
      Components.skeletonHTML('line', 4) +
      '    </div>' +
      '  </div>' +
      '</div>' +
      '<div class="content-grid" style="margin-top: var(--space-4);">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Plugins / Analisadores</span></div>' +
      '    <div class="card-body" id="healthPluginsBody">' +
      Components.skeletonHTML('line', 4) +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Mini Gr\u00e1ficos</span></div>' +
      '    <div class="card-body" id="healthChartsBody">' +
      Components.skeletonHTML('bar', 3) +
      '    </div>' +
      '  </div>' +
      '</div>'
    );
  },
  onLoad: function () {
    HealthPage._refreshHandler = function () { HealthPage.refresh(); };
    document.addEventListener('edy-refresh', HealthPage._refreshHandler);
    HealthPage.refresh();
  },

  onUnload: function () {
    if (HealthPage._refreshHandler) {
      document.removeEventListener('edy-refresh', HealthPage._refreshHandler);
      HealthPage._refreshHandler = null;
    }
    if (Router.abortFetch) Router.abortFetch();
  }
});

var HealthPage = {
  refresh: function () {
    Promise.all([
      EDY.api('/api/health'),
      EDY.api('/api/plugins')
    ])
      .then(function (results) {
        var h = results[0];
        var plugins = results[1] || {};
        var pList = (plugins.plugins || []).filter(function (p) { return p && p.name; });

        // Última atualização
        var upd = document.getElementById('healthUpdated');
        if (upd) {
          upd.textContent = 'Última atualização: ' + new Date().toLocaleTimeString('pt-BR');
        }

        HealthPage._renderKPIs(h, pList);
        HealthPage._renderServices(h);
        HealthPage._renderEngine(h);
        HealthPage._renderPlugins(pList);
        HealthPage._renderCharts(h);
      })
      .catch(function (err) {
        var body = document.getElementById('healthComponentsBody');
        if (body) body.innerHTML = Components.errorStateHTML('Erro ao carregar', err.message);
      });
  },

  _renderKPIs: function (h, pList) {
    var grid = document.getElementById('healthKpiGrid');
    if (!grid) return;
    var dbOk = h.sqlite && h.sqlite.status === 'ok';
    var apiOk = h.status === 'online';
    grid.innerHTML = '' +
      Components.statCardHTML({ label: 'API', value: apiOk ? 'Online' : 'Degradado', severity: apiOk ? 'low' : 'critical', icon: '\u21BA' }) +
      Components.statCardHTML({ label: 'Database', value: dbOk ? 'Saud\u00e1vel' : 'Erro', severity: dbOk ? 'low' : 'critical', icon: '\u2637' }) +
      Components.statCardHTML({ label: 'Analyzers', value: pList.length + ' ativos', severity: pList.length > 0 ? 'low' : 'medium', icon: '\u2731' }) +
      Components.statCardHTML({ label: 'Uptime', value: HealthPage._formatUptime(h.uptime_seconds || 0), severity: 'info', icon: '\u23F1' });
  },

  _renderServices: function (h) {
    var body = document.getElementById('healthComponentsBody');
    if (!body) return;
    var dbOk = h.sqlite && h.sqlite.status === 'ok';
    var apiOk = h.status === 'online';
    body.innerHTML = '' +
      HealthPage._svcRow('API REST', apiOk ? 'Operacional' : 'Degradado', apiOk ? 'resolved' : 'suppressed') +
      HealthPage._svcRow('Banco de Dados (SQLite)', dbOk ? 'Saud\u00e1vel' : 'Erro', dbOk ? 'resolved' : 'suppressed') +
      HealthPage._svcRow('Alert Engine', h.alert_engine ? 'Ativo' : 'Indispon\u00edvel', h.alert_engine ? 'resolved' : 'suppressed') +
      HealthPage._svcRow('Python', h.python_version || '—', 'info') +
      HealthPage._svcRow('Plataforma', (h.platform || '—').split('|')[0].trim(), 'info');
  },

  _svcRow: function (label, value, badgeCls) {
    var cls = badgeCls === 'resolved' ? 'badge-status-resolved'
      : badgeCls === 'suppressed' ? 'badge-status-suppressed' : 'badge-status-new';
    return '<div class="health-svc-row">' +
      '<span class="health-svc-label">' + Components.escape(label) + '</span>' +
      '<span class="badge ' + cls + '">' + Components.escape(value) + '</span></div>';
  },

  _renderEngine: function (h) {
    var body = document.getElementById('healthEngineBody');
    if (!body || !h.alert_engine) return;
    var e = h.alert_engine;
    body.innerHTML = '' +
      HealthPage._statRow('Eventos Processados', e.events_processed || 0) +
      HealthPage._statRow('Alertas Criados', e.alerts_created || 0) +
      HealthPage._statRow('Alertas Deduplicados', e.alerts_deduplicated || 0) +
      HealthPage._statRow('Cache de Dedup', h.dedup_cache_size || 0) +
      '<div class="health-bar" style="margin-top: 12px;">' +
      '  <div class="health-bar-header"><span class="health-bar-label">Status</span><span class="health-bar-value">' +
      Components.escape((h.status || 'online').toUpperCase()) + '</span></div>' +
      '  <div class="health-bar-track"><div class="health-bar-fill good" style="width: 100%;"></div></div>' +
      '</div>';
  },

  _statRow: function (label, value) {
    return '<div class="health-stat-row">' +
      '<span>' + Components.escape(label) + '</span><strong>' + value + '</strong></div>';
  },

  _renderPlugins: function (pList) {
    var body = document.getElementById('healthPluginsBody');
    if (!body) return;
    if (pList.length === 0) {
      body.innerHTML = Components.emptyStateHTML('\u2731', 'Nenhum plugin', 'Nenhum analisador registrado.');
      return;
    }
    body.innerHTML = '<div class="plugin-list">' + pList.map(function (p) {
      return '<div class="plugin-item">' +
        '<span class="plugin-item-dot"></span>' +
        '<span class="plugin-item-name">' + Components.escape(p.name) + '</span>' +
        '<span class="badge badge-status-resolved">Ativo</span></div>';
    }).join('') + '</div>';
  },

  _renderCharts: function (h) {
    var body = document.getElementById('healthChartsBody');
    if (!body) return;
    var e = h.alert_engine || {};
    var created = e.alerts_created || 0;
    var processed = e.events_processed || 0;
    var dedup = e.alerts_deduplicated || 0;
    var maxVal = Math.max(1, processed, created * 5, dedup * 5);
    body.innerHTML = '<div class="bar-chart">' +
      HealthPage._miniBar('Eventos Processados', processed, Math.round(processed / maxVal * 100), 'status-new') +
      HealthPage._miniBar('Alertas Criados', created, Math.round(created / maxVal * 100), 'status-ack') +
      HealthPage._miniBar('Deduplicados', dedup, Math.round(dedup / maxVal * 100), 'status-resolved') +
      '</div>';
  },

  _miniBar: function (label, value, pct, cls) {
    return '<div class="bar-chart-row">' +
      '<span class="bar-chart-label">' + Components.escape(label) + '</span>' +
      '<div class="bar-chart-track">' +
      '<div class="bar-chart-fill ' + cls + '" style="width: ' + Math.max(2, Math.min(100, pct)) + '%;">' +
      (pct > 25 ? value : '') + '</div></div>' +
      '<span class="bar-chart-value">' + value + '</span></div>';
  },

  _formatUptime: function (seconds) {
    if (!seconds || seconds < 0) return '-';
    var d = Math.floor(seconds / 86400);
    var h = Math.floor((seconds % 86400) / 3600);
    var m = Math.floor((seconds % 3600) / 60);
    var s = Math.floor(seconds % 60);
    var parts = [];
    if (d > 0) parts.push(d + 'd');
    if (h > 0) parts.push(h + 'h');
    if (m > 0) parts.push(m + 'm');
    parts.push(s + 's');
    return parts.join(' ');
  }
};
