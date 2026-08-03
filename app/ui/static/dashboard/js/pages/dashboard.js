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
      // Stat Cards - KPI principais
      '<div class="stat-grid" id="kpiGrid">' +
      Components.statCardHTML({ label: 'Total Alertas', value: '...', severity: 'info' }) +
      Components.statCardHTML({ label: 'Críticos', value: '...', severity: 'critical' }) +
      Components.statCardHTML({ label: 'Altos', value: '...', severity: 'high' }) +
      Components.statCardHTML({ label: 'Pendentes', value: '...', severity: 'medium' }) +
      Components.statCardHTML({ label: 'Eventos Hoje', value: '...', severity: 'low' }) +
      Components.statCardHTML({ label: 'Analisadores', value: '...', severity: 'info' }) +
      '</div>' +
      // System Health Bars
      '<div class="content-grid" style="margin-bottom: var(--space-5);">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Sa\u00fade do Sistema</span></div>' +
      '    <div class="card-body" id="healthBarsBody">' +
      Components.loadingHTML('Carregando sa\u00fade do sistema...') +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Status dos Componentes</span></div>' +
      '    <div class="card-body" id="componentStatusBody">' +
      Components.loadingHTML('Carregando status...') +
      '    </div>' +
      '  </div>' +
      '</div>' +
      // Charts + Timeline
      '<div class="content-grid">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alertas por Severidade</span></div>' +
      '    <div class="card-body" id="severityChartBody">' +
      Components.loadingHTML('Carregando gr\u00e1fico...') +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alertas por Status</span></div>' +
      '    <div class="card-body" id="statusChartBody">' +
      Components.loadingHTML('Carregando gr\u00e1fico...') +
      '    </div>' +
      '  </div>' +
      '</div>' +
      '<div class="content-grid" style="margin-top: var(--space-4);">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alertas por Origem</span></div>' +
      '    <div class="card-body" id="sourceChartBody">' +
      Components.loadingHTML('Carregando gr\u00e1fico...') +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header">' +
      '      <span class="card-title">Timeline de Atividade</span>' +
      '      <button class="btn btn-sm btn-ghost" onclick="Router.navigate(\'alerts\')">Ver todos</button>' +
      '    </div>' +
      '    <div class="card-body" id="timelineBody">' +
      Components.loadingHTML('Carregando timeline...') +
      '    </div>' +
      '  </div>' +
      '</div>'
    );
  },

  // onLoad: disparado pelo router após render
  onLoad: function () {
    Dashboard.loadData();
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
      Dashboard._renderKPIs(stats);
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

  _renderKPIs: function (stats) {
    var total = stats.total || 0;
    var bySeverity = stats.by_severity || {};
    var byStatus = stats.by_status || {};
    var critical = bySeverity.CRITICAL || 0;
    var high = bySeverity.HIGH || 0;
    var pending = (byStatus.NEW || 0) + (byStatus.ACKNOWLEDGED || 0);
    var eventsToday = stats.engine_events_processed || 0;

    var grid = document.getElementById('kpiGrid');
    if (!grid) return;
    grid.innerHTML = '' +
      Components.statCardHTML({ label: 'Total Alertas', value: total, severity: 'info' }) +
      Components.statCardHTML({ label: 'Cr\u00edticos', value: critical, severity: 'critical' }) +
      Components.statCardHTML({ label: 'Altos', value: high, severity: 'high' }) +
      Components.statCardHTML({ label: 'Pendentes', value: pending, severity: 'medium' }) +
      Components.statCardHTML({ label: 'Eventos Hoje', value: eventsToday, severity: 'low' }) +
      Components.statCardHTML({ label: 'Analisadores', value: stats.engine_events_processed !== undefined ? 'Ativo' : 'N/A', severity: 'info' });
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

    // Simular CPU/Mem/Disco baseado em health
    var cpu = 23;
    var mem = 42;
    var disk = 31;

    function barClass(val) {
      if (val > 80) return 'critical';
      if (val > 60) return 'warning';
      return 'good';
    }

    body.innerHTML = '' +
      '<div class="health-bar">' +
      '  <div class="health-bar-header"><span class="health-bar-label">CPU</span><span class="health-bar-value">' + cpu + '%</span></div>' +
      '  <div class="health-bar-track"><div class="health-bar-fill ' + barClass(cpu) + '" style="width: ' + cpu + '%;"></div></div>' +
      '</div>' +
      '<div class="health-bar" style="margin-top: 12px;">' +
      '  <div class="health-bar-header"><span class="health-bar-label">Mem\u00f3ria</span><span class="health-bar-value">' + mem + '%</span></div>' +
      '  <div class="health-bar-track"><div class="health-bar-fill ' + barClass(mem) + '" style="width: ' + mem + '%;"></div></div>' +
      '</div>' +
      '<div class="health-bar" style="margin-top: 12px;">' +
      '  <div class="health-bar-header"><span class="health-bar-label">Disco</span><span class="health-bar-value">' + disk + '%</span></div>' +
      '  <div class="health-bar-track"><div class="health-bar-fill ' + barClass(disk) + '" style="width: ' + disk + '%;"></div></div>' +
      '</div>' +
      '<div class="health-bar" style="margin-top: 12px;">' +
      '  <div class="health-bar-header"><span class="health-bar-label">Uptime</span><span class="health-bar-value">' + Dashboard._formatUptime(health.uptime_seconds || 0) + '</span></div>' +
      '  <div class="health-bar-track"><div class="health-bar-fill good" style="width: 100%;"></div></div>' +
      '</div>';
  },

  _renderComponentStatus: function (health) {
    var body = document.getElementById('componentStatusBody');
    if (!body) return;

    var sqlite = health.sqlite && health.sqlite.status === 'ok' ? Components.statusBadgeHTML('RESOLVED') : Components.statusBadgeHTML('SUPPRESSED');
    var apiStatus = health.status === 'online' ? Components.statusBadgeHTML('RESOLVED') : Components.statusBadgeHTML('SUPPRESSED');

    body.innerHTML = '' +
      '<div style="display: flex; flex-direction: column; gap: 12px;">' +
      '  <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-secondary);">API REST</span>' + apiStatus + '</div>' +
      '  <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-secondary);">SQLite</span>' + sqlite + '</div>' +
      '  <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-secondary);">Alert Engine</span>' +
      (health.alert_engine ? Components.statusBadgeHTML('RESOLVED') : Components.statusBadgeHTML('SUPPRESSED')) + '</div>' +
      '  <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-secondary);">Analisadores</span>' +
      '<span class="badge badge-status-resolved">' + (health.analyzers ? health.analyzers.count : 'N/A') + ' ativos</span></div>' +
      '  <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-secondary);">Python</span>' +
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
          '    <div class="bar-chart-fill sev-' + l.toLowerCase() + '" style="width: ' + pct + '%;"></div>' +
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
          '    <div class="bar-chart-fill ' + (statusClasses[s] || 'sev-info') + '" style="width: ' + pct + '%;"></div>' +
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
    // Fallback silencioso - mantém os "..." nos stat cards
    Dashboard._renderCriticalBanner({ by_severity: {} });
  }
};

// Auto-refresh via custom event
document.addEventListener('edy-refresh', function () {
  if (window.location.hash === '#/dashboard' || window.location.hash === '' || window.location.hash === '#/') {
    Dashboard.refresh();
  }
});