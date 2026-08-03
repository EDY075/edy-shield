/**
 * EDY Shield Dashboard — Página Alert Center (M4.2)
 * Central de alertas com dados reais, filtros e actions via API.
 */

Router.register('alerts', {
  title: 'Alert Center',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>Alert Center</h1>' +
      '    <p>Gerencie e triage alertas do motor de alertas</p>' +
      '  </div>' +
      '  <div style="display: flex; gap: 8px;">' +
      '    <button class="btn" onclick="AlertsPage.refresh()">Atualizar</button>' +
      '  </div>' +
      '</div>' +
      '<div class="stat-grid" id="alertsKpiGrid">' +
      Components.statCardHTML({ label: 'Novos', value: '...', severity: 'low' }) +
      Components.statCardHTML({ label: 'Reconhecidos', value: '...', severity: 'medium' }) +
      Components.statCardHTML({ label: 'Resolvidos', value: '...', severity: 'info' }) +
      Components.statCardHTML({ label: 'Suprimidos', value: '...', severity: 'info' }) +
      '</div>' +
      '<div class="card">' +
      '  <div class="card-header">' +
      '    <span class="card-title">Todos os Alertas</span>' +
      '    <div style="display: flex; gap: 8px;">' +
      '      <select class="btn" style="min-width: 120px;" id="severityFilter" onchange="AlertsPage.filter()">' +
      '        <option value="">Todas Severidades</option>' +
      '        <option value="CRITICAL">CRITICAL</option>' +
      '        <option value="HIGH">HIGH</option>' +
      '        <option value="MEDIUM">MEDIUM</option>' +
      '        <option value="LOW">LOW</option>' +
      '        <option value="INFO">INFO</option>' +
      '      </select>' +
      '      <select class="btn" style="min-width: 120px;" id="statusFilter" onchange="AlertsPage.filter()">' +
      '        <option value="">Todos Status</option>' +
      '        <option value="NEW">NEW</option>' +
      '        <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>' +
      '        <option value="RESOLVED">RESOLVED</option>' +
      '        <option value="SUPPRESSED">SUPPRESSED</option>' +
      '      </select>' +
      '    </div>' +
      '  </div>' +
      '  <div class="card-body" id="alertsTableBody">' +
      Components.loadingHTML('Carregando alertas...') +
      '  </div>' +
      '</div>'
    );
  },
  onLoad: function () {
    AlertsPage.refresh();
  }
});

var AlertsPage = {
  refresh: function () {
    AlertsPage._loadStats();
    AlertsPage._loadAlerts();
  },

  filter: function () {
    AlertsPage._loadAlerts();
  },

  _loadStats: function () {
    EDY.api('/api/alerts/stats')
      .then(function (stats) {
        var byStatus = stats.by_status || {};
        var grid = document.getElementById('alertsKpiGrid');
        if (!grid) return;
        grid.innerHTML = '' +
          Components.statCardHTML({ label: 'Novos', value: byStatus.NEW || 0, severity: 'low' }) +
          Components.statCardHTML({ label: 'Reconhecidos', value: byStatus.ACKNOWLEDGED || 0, severity: 'medium' }) +
          Components.statCardHTML({ label: 'Resolvidos', value: byStatus.RESOLVED || 0, severity: 'info' }) +
          Components.statCardHTML({ label: 'Suprimidos', value: byStatus.SUPPRESSED || 0, severity: 'info' });
      })
      .catch(function () {});
  },

  _loadAlerts: function () {
    var sev = document.getElementById('severityFilter') ? document.getElementById('severityFilter').value : '';
    var status = document.getElementById('statusFilter') ? document.getElementById('statusFilter').value : '';
    var params = '?limit=50';
    if (sev) params += '&severity=' + sev;
    if (status) params += '&status=' + status;

    EDY.api('/api/alerts' + params)
      .then(function (data) {
        var body = document.getElementById('alertsTableBody');
        if (!body) return;
        var alerts = data.alerts || [];
        if (alerts.length === 0) {
          body.innerHTML = Components.tableHTML({
            columns: [
              { key: 'severity', label: 'Severidade', render: function (r) { return Components.severityBadgeHTML(r.severity); } },
              { key: 'status', label: 'Status', render: function (r) { return Components.statusBadgeHTML(r.status); } },
              { key: 'title', label: 'Título' },
              { key: 'source', label: 'Origem' },
              { key: 'target', label: 'Alvo' },
              { key: 'count', label: 'Count' },
              { key: 'last_seen_at', label: 'Última Ocorrência' }
            ],
            rows: []
          });
          return;
        }
        body.innerHTML = Components.tableHTML({
          columns: [
            { key: 'severity', label: 'Severidade', render: function (r) { return Components.severityBadgeHTML(r.severity); } },
            { key: 'status', label: 'Status', render: function (r) { return Components.statusBadgeHTML(r.status); } },
            { key: 'title', label: 'T\u00edtulo' },
            { key: 'source', label: 'Origem' },
            { key: 'target', label: 'Alvo' },
            { key: 'count', label: 'Count' },
            { key: 'last_seen_at', label: '\u00daltima Ocorr\u00eancia' }
          ],
          rows: alerts.map(function (a) {
            return {
              severity: a.severity,
              status: a.status,
              title: a.title || a.rule_id || '-',
              source: a.source || '-',
              target: a.target || '-',
              count: a.count || 1,
              last_seen_at: a.last_seen_at ? a.last_seen_at.slice(0, 19).replace('T', ' ') : '-'
            };
          })
        });
      })
      .catch(function (err) {
        var body = document.getElementById('alertsTableBody');
        if (body) body.innerHTML = Components.errorStateHTML('Erro ao carregar', err.message);
      });
  }
};