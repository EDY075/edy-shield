/**
 * EDY Shield Dashboard — Página Dashboard (M4.2 - Blue Team Overview)
 * Central operacional completa para uso diário de Blue Team.
 * Dados reais via API REST. Auto-refresh, gráficos, timeline, quick actions.
 */

Router.register('dashboard', {
  title: 'Dashboard',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>Dashboard</h1>' +
      '    <p>Central operacional Blue Team &mdash; dados em tempo real</p>' +
      '  </div>' +
      '  <div style="display: flex; gap: 8px; align-items: center;">' +
      '    <div class="period-filter" id="periodFilter">' +
      '      <button class="period-filter-btn" data-period="1h">1h</button>' +
      '      <button class="period-filter-btn active" data-period="24h">24h</button>' +
      '      <button class="period-filter-btn" data-period="7d">7d</button>' +
      '      <button class="period-filter-btn" data-period="30d">30d</button>' +
      '    </div>' +
      '    <div class="refresh-indicator">' +
      '      <span class="refresh-spinner" id="refreshSpinner"></span>' +
      '      <span id="refreshText">Auto</span>' +
      '    </div>' +
      '    <button class="btn btn-primary btn-sm" onclick="Dashboard.refresh()">Atualizar</button>' +
      '  </div>' +
      '</div>' +
      // Critical Banner (hidden by default)
      '<div class="critical-banner" id="criticalBanner" style="display: none;">' +
      '  <span class="critical-banner-icon">&#9888;</span>' +
      '  <div class="critical-banner-text">' +
      '    <strong id="criticalCount">0</strong> alertas críticos requerem aten\u00e7\u00e3o imediata.' +
      '  </div>' +
      '  <button class="btn btn-sm" onclick="Router.navigate(\'alerts\')">Ver Alertas</button>' +
      '</div>' +
      // Quick Actions
      '<div class="quick-actions">' +
      '  <button class="quick-action-btn" onclick="Router.navigate(\'health\')">' +
      '    <span class="quick-action-icon">&#9881;</span> Novo Scan' +
      '  </button>' +
      '  <button class="quick-action-btn" onclick="Router.navigate(\'alerts\')">' +
      '    <span class="quick-action-icon">&#9888;</span> Ver Alertas' +
      '  </button>' +
      '  <button class="quick-action-btn" onclick="Router.navigate(\'ioc\')">' +
      '    <span class="quick-action-icon">&#9888;</span> Importar IOC' +
      '  </button>' +
      '  <button class="quick-action-btn" onclick="Router.navigate(\'logs\')">' +
      '    <span class="quick-action-icon">&#9776;</span> Abrir Logs' +
      '  </button>' +
      '  <button class="quick-action-btn" onclick="Dashboard.refresh()">' +
      '    <span class="quick-action-icon">&#10227;</span> Atualizar Dashboard' +
      '  </button>' +
      '</div>' +
      // Stat Cards - KPI principais (M4.4.4 skeleton) — 5 KPIs como referência
      '<div class="stat-grid" id="kpiGrid">' +
      Components.skeletonHTML('card', 5) +
      '</div>' +
      // System Health Bars
      '<div class="content-grid" style="margin-bottom: var(--space-5);">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Sa\u00fade do Sistema</span></div>' +
      '    <div class="card-body" id="healthBarsBody">' +
      Components.skeletonHTML('bar', 4) +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Status dos Componentes</span></div>' +
      '    <div class="card-body" id="componentStatusBody">' +
      Components.skeletonHTML('line', 5) +
      '    </div>' +
      '  </div>' +
      '</div>' +
      // Charts + Timeline
      '<div class="content-grid">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alertas por Severidade</span></div>' +
      '    <div class="card-body" id="severityChartBody">' +
      Components.skeletonHTML('bar', 5) +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alertas por Status</span></div>' +
      '    <div class="card-body" id="statusChartBody">' +
      Components.skeletonHTML('bar', 4) +
      '    </div>' +
      '  </div>' +
      '</div>' +
      '<div class="content-grid" style="margin-top: var(--space-4);">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alertas por Origem</span></div>' +
      '    <div class="card-body" id="sourceChartBody">' +
      Components.skeletonHTML('bar', 4) +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header">' +
      '      <span class="card-title">Timeline de Atividade</span>' +
      '      <button class="btn btn-sm btn-ghost" onclick="Router.navigate(\'alerts\')">Ver todos</button>' +
      '    </div>' +
      '    <div class="card-body" id="timelineBody">' +
      Components.skeletonHTML('line', 5) +
      '    </div>' +
      '  </div>' +
      '</div>'
    );
  },

  // onLoad: disparado pelo router após render
  onLoad: function () {
    // Registrar listener de refresh remov\u00edvel
    Dashboard._refreshHandler = function () { Dashboard.refresh(); };
    document.addEventListener('edy-refresh', Dashboard._refreshHandler);
    // Carregar dados
    Dashboard.loadData();
  },

  // onUnload: limpeza antes de sair da p\u00e1gina
  onUnload: function () {
    if (Dashboard._refreshHandler) {
      document.removeEventListener('edy-refresh', Dashboard._refreshHandler);
      Dashboard._refreshHandler = null;
    }
    // Cancelar fetch pendente via router
    if (Router.abortFetch) Router.abortFetch();
  }
});

var Dashboard = {
  refresh: function () {
    Dashboard._startSpinner();
    Dashboard.loadData();
  },

  loadData: function () {
    // Carregar alert stats + health + timeline em paralelo
    Promise.all([
      EDY.api('/api/alerts/stats'),
      EDY.api('/api/health')
    ])
    .then(function (results) {
      var stats = results[0];
      var health = results[1];
      Dashboard._renderKPIs(stats, health);
      Dashboard._renderCriticalBanner(stats);
      Dashboard._renderHealthBars(health);
      Dashboard._renderComponentStatus(health);
      Dashboard._renderSeverityChart(stats);
      Dashboard._renderStatusChart(stats);
      Dashboard._renderSourceChart(stats);
      Dashboard._renderTimeline(stats, health);
    })
    .catch(function (err) {
      Dashboard._fallbackData();
      Toast.error('Erro ao carregar dados: ' + err.message);
    })
    .finally(function () {
      Dashboard._stopSpinner();
    });
  },

  _renderKPIs: function (stats, health) {
    var total = stats.total || 0;
    var bySeverity = stats.by_severity || {};
    var byStatus = stats.by_status || {};
    var critical = bySeverity.CRITICAL || 0;
    var high = bySeverity.HIGH || 0;
    var pending = (byStatus.NEW || 0) + (byStatus.ACKNOWLEDGED || 0);
    var resolved = byStatus.RESOLVED || 0;

    var grid = document.getElementById('kpiGrid');
    if (!grid) return;
    var defs = [
      { label: 'Total Alertas', value: total, sev: 'info', icon: '\u2637', key: 'total' },
      { label: 'Cr\u00edticos', value: critical, sev: 'critical', icon: '\u26A0', key: 'critical' },
      { label: 'Altos', value: high, sev: 'high', icon: '\u21D1', key: 'high' },
      { label: 'Pendentes', value: pending, sev: 'medium', icon: '\u25CB', key: 'pending' },
      { label: 'Resolvidos', value: resolved, sev: 'info', icon: '\u2713', key: 'resolved' }
    ];
    var maxVal = Math.max(1, total, critical, high, pending, resolved);
    grid.innerHTML = defs.map(function (d) {
      var pct = Math.round((d.value || 0) / maxVal * 100);
      return '<div class="stat-card severity-' + d.sev + '">' +
        '<div class="stat-card-top">' +
        '  <div class="stat-card-icon severity-' + d.sev + '">' + d.icon + '</div>' +
        '  <div class="stat-card-label">' + d.label + '</div>' +
        '</div>' +
        '<div class="stat-card-value">' + d.value + '</div>' +
        '<div class="stat-card-minibar"><div class="stat-card-minibar-fill sev-' + d.sev + '" style="width: ' + pct + '%;"></div></div>' +
        '</div>';
    }).join('');
  },

  _renderCriticalBanner: function (stats) {
    var bySeverity = stats.by_severity || {};
    var critical = bySeverity.CRITICAL || 0;
    var banner = document.getElementById('criticalBanner');
    if (!banner) return;
    if (critical > 0) {
      banner.style.display = 'flex';
      document.getElementById('criticalCount').textContent = critical;
    } else {
      banner.style.display = 'none';
    }
  },

  _renderHealthBars: function (health) {
    var body = document.getElementById('healthBarsBody');
    if (!body) return;

    // Dados reais da API — sem simulação
    var sqliteOk = health.sqlite && health.sqlite.status === 'ok';
    var analyzerCount = health.analyzers ? health.analyzers.count : 0;
    var engine = health.alert_engine || {};
    var events = engine.events_processed || 0;
    var dedup = engine.alerts_deduplicated || 0;

    function barClass(val) {
      if (val > 80) return 'critical';
      if (val > 60) return 'warning';
      return 'good';
    }

    var sqlitePct = sqliteOk ? 100 : 0;
    var eventsPct = Math.min(100, Math.round(events / 1000 * 100));

    body.innerHTML = '' +
      '<div class="health-bar">' +
      '  <div class="health-bar-header"><span class="health-bar-label">SQLite</span><span class="health-bar-value">' + (sqliteOk ? 'Operacional' : 'Erro') + '</span></div>' +
      '  <div class="health-bar-track"><div class="health-bar-fill ' + (sqliteOk ? 'good' : 'critical') + '" style="width: ' + sqlitePct + '%;"></div></div>' +
      '</div>' +
      '<div class="health-bar" style="margin-top: 12px;">' +
      '  <div class="health-bar-header"><span class="health-bar-label">Analisadores</span><span class="health-bar-value">' + analyzerCount + ' ativos</span></div>' +
      '  <div class="health-bar-track"><div class="health-bar-fill ' + (analyzerCount > 0 ? 'good' : 'critical') + '" style="width: ' + Math.min(100, analyzerCount * 20) + '%;"></div></div>' +
      '</div>' +
      '<div class="health-bar" style="margin-top: 12px;">' +
      '  <div class="health-bar-header"><span class="health-bar-label">Eventos Processados</span><span class="health-bar-value">' + events + '</span></div>' +
      '  <div class="health-bar-track"><div class="health-bar-fill good" style="width: ' + eventsPct + '%;"></div></div>' +
      '</div>' +
      '<div class="health-bar" style="margin-top: 12px;">' +
      '  <div class="health-bar-header"><span class="health-bar-label">Uptime</span><span class="health-bar-value">' + Dashboard._formatUptime(health.uptime_seconds || 0) + '</span></div>' +
      '  <div class="health-bar-track"><div class="health-bar-fill good" style="width: 100%;"></div></div>' +
      '</div>';
  },

  _renderComponentStatus: function (health) {
    var body = document.getElementById('componentStatusBody');
    if (!body) return;

    function ptBadge(ok, okLabel, badLabel) {
      return '<span class="badge ' + (ok ? 'badge-status-resolved' : 'badge-status-suppressed') + '">' + (ok ? okLabel : badLabel) + '</span>';
    }

    var sqliteOk = health.sqlite && health.sqlite.status === 'ok';
    var apiOk = health.status === 'online';
    var analyzerCount = health.analyzers ? health.analyzers.count : 0;

    body.innerHTML = '' +
      '<div style="display: flex; flex-direction: column; gap: 12px;">' +
      '  <div style="display: flex; justify-content: space-between; align-items: center;"><span style="color: var(--text-secondary);">API REST</span>' + ptBadge(apiOk, 'Operacional', 'Degradado') + '</div>' +
      '  <div style="display: flex; justify-content: space-between; align-items: center;"><span style="color: var(--text-secondary);">Banco de Dados</span>' + ptBadge(sqliteOk, 'Saud\u00e1vel', 'Erro') + '</div>' +
      '  <div style="display: flex; justify-content: space-between; align-items: center;"><span style="color: var(--text-secondary);">Alert Engine</span>' + ptBadge(!!health.alert_engine, 'Ativo', 'Inativo') + '</div>' +
      '  <div style="display: flex; justify-content: space-between; align-items: center;"><span style="color: var(--text-secondary);">Analisadores</span>' +
      '<span class="badge badge-status-resolved">' + analyzerCount + ' ativos</span></div>' +
      '  <div style="display: flex; justify-content: space-between; align-items: center;"><span style="color: var(--text-secondary);">Python</span>' +
      '<span style="color: var(--text-primary); font-size: 12px;">' + (health.python_version || 'N/A') + '</span></div>' +
      '</div>';
  },

  _renderSeverityChart: function (stats) {
    var body = document.getElementById('severityChartBody');
    if (!body) return;
    var bySeverity = stats.by_severity || {};
    var levels = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'];
    var maxVal = Math.max(1, Math.max.apply(null, levels.map(function (l) { return bySeverity[l] || 0; })));

    body.innerHTML = '<div class="bar-chart">' +
      levels.map(function (l) {
        var val = bySeverity[l] || 0;
        var pct = Math.round(val / maxVal * 100);
        return '' +
          '<div class="bar-chart-row">' +
          '  <span class="bar-chart-label">' + l + '</span>' +
          '  <div class="bar-chart-track">' +
          '    <div class="bar-chart-fill sev-' + l.toLowerCase() + '" style="width: ' + pct + '%;">' +
          (pct > 25 ? val : '') +
          '    </div>' +
          '  </div>' +
          '  <span class="bar-chart-value">' + val + '</span>' +
          '</div>';
      }).join('') +
      '</div>';
  },

  _renderStatusChart: function (stats) {
    var body = document.getElementById('statusChartBody');
    if (!body) return;
    var byStatus = stats.by_status || {};
    var statuses = ['NEW', 'ACKNOWLEDGED', 'RESOLVED', 'SUPPRESSED'];
    var statusLabels = { NEW: 'Novos', ACKNOWLEDGED: 'Reconhecidos', RESOLVED: 'Resolvidos', SUPPRESSED: 'Suprimidos' };
    var statusClasses = { NEW: 'status-new', ACKNOWLEDGED: 'status-ack', RESOLVED: 'status-resolved', SUPPRESSED: 'status-suppressed' };
    var maxVal = Math.max(1, Math.max.apply(null, statuses.map(function (s) { return byStatus[s] || 0; })));

    body.innerHTML = '<div class="bar-chart">' +
      statuses.map(function (s) {
        var val = byStatus[s] || 0;
        var pct = Math.round(val / maxVal * 100);
        return '' +
          '<div class="bar-chart-row">' +
          '  <span class="bar-chart-label">' + (statusLabels[s] || s) + '</span>' +
          '  <div class="bar-chart-track">' +
          '    <div class="bar-chart-fill ' + (statusClasses[s] || 'sev-info') + '" style="width: ' + pct + '%;">' +
          (pct > 25 ? val : '') +
          '    </div>' +
          '  </div>' +
          '  <span class="bar-chart-value">' + val + '</span>' +
          '</div>';
      }).join('') +
      '</div>';
  },

  _renderSourceChart: function (stats) {
    var body = document.getElementById('sourceChartBody');
    if (!body) return;
    var bySource = stats.by_source || {};
    var sources = Object.keys(bySource);
    if (sources.length === 0) {
      body.innerHTML = Components.emptyStateHTML('\u2261', 'Sem dados de origem', 'Nenhum alerta registrado por origem.');
      return;
    }
    var maxVal = Math.max(1, Math.max.apply(null, sources.map(function (s) { return bySource[s] || 0; })));

    body.innerHTML = '<div class="bar-chart">' +
      sources.map(function (s) {
        var val = bySource[s] || 0;
        var pct = Math.round(val / maxVal * 100);
        return '' +
          '<div class="bar-chart-row">' +
          '  <span class="bar-chart-label">' + Components.escape(s) + '</span>' +
          '  <div class="bar-chart-track">' +
          '    <div class="bar-chart-fill sev-info" style="width: ' + pct + '%;">' +
          (pct > 30 ? Components.escape(String(val)) : '') +
          '    </div>' +
          '  </div>' +
          '  <span class="bar-chart-value">' + val + '</span>' +
          '</div>';
      }).join('') +
      '</div>';
  },

  _renderTimeline: function (stats, health) {
    var body = document.getElementById('timelineBody');
    if (!body) return;

    // Montar timeline a partir de alertas via API
    EDY.api('/api/alerts?limit=10')
      .then(function (data) {
        var alerts = data.alerts || [];
        if (alerts.length === 0) {
          body.innerHTML = Components.emptyStateHTML('\u2205', 'Nenhuma atividade recente', 'Alertas aparecer\u00e3o aqui conforme forem gerados.');
          return;
        }
        body.innerHTML = '<div class="timeline">' +
          alerts.map(function (a) {
            var sev = (a.severity || 'info').toLowerCase();
            var time = a.last_seen_at ? a.last_seen_at.split('T')[1] || a.last_seen_at : '';
            return '' +
              '<div class="timeline-item">' +
              '  <div class="timeline-dot ' + sev + '">&#9679;</div>' +
              '  <div class="timeline-content">' +
              '    <div class="timeline-title">' + Components.escape(a.title || a.rule_id || 'Alerta') + '</div>' +
              '    <div class="timeline-meta">' +
              Components.severityBadgeHTML(a.severity) +
              '      <span>' + Components.escape(time) + '</span>' +
              '      <span>' + Components.escape(a.source || '') + '</span>' +
              '    </div>' +
              '  </div>' +
              '</div>';
          }).join('') +
          '</div>';
      })
      .catch(function () {
        body.innerHTML = Components.errorStateHTML('Erro ao carregar timeline', 'N\u00e3o foi poss\u00edvel obter a timeline de atividade.');
      });
  },

  _startSpinner: function () {
    var spinner = document.getElementById('refreshSpinner');
    if (spinner) spinner.classList.add('active');
    var text = document.getElementById('refreshText');
    if (text) text.textContent = 'Atualizando...';
  },

  _stopSpinner: function () {
    var spinner = document.getElementById('refreshSpinner');
    if (spinner) spinner.classList.remove('active');
    var text = document.getElementById('refreshText');
    if (text) text.textContent = 'Auto';
  },

  _formatUptime: function (seconds) {
    if (!seconds) return '-';
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
  },

  _fallbackData: function () {
    // Fallback silencioso - mant\u00e9m os "..." nos stat cards
    Dashboard._renderCriticalBanner({ by_severity: {} });
  }
};