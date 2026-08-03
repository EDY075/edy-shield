/**
 * EDY Shield Dashboard — Página Alert Center (M4.1)
 * Central de alertas com filtros e tabela.
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
      '    <button class="btn">Exportar</button>' +
      '    <button class="btn btn-primary">Novo Alerta</button>' +
      '  </div>' +
      '</div>' +
      '<div class="stat-grid">' +
      Components.statCardHTML({ label: 'Novos', value: '—', severity: 'low' }) +
      Components.statCardHTML({ label: 'Reconhecidos', value: '—', severity: 'medium' }) +
      Components.statCardHTML({ label: 'Resolvidos', value: '—', severity: 'info' }) +
      Components.statCardHTML({ label: 'Suprimidos', value: '—', severity: 'info' }) +
      '</div>' +
      '<div class="card">' +
      '  <div class="card-header">' +
      '    <span class="card-title">Todos os Alertas</span>' +
      '    <div style="display: flex; gap: 8px;">' +
      '      <select class="btn" style="min-width: 120px;"><option>Todas Severidades</option><option>CRITICAL</option><option>HIGH</option><option>MEDIUM</option><option>LOW</option></select>' +
      '      <select class="btn" style="min-width: 120px;"><option>Todos Status</option><option>NEW</option><option>ACKNOWLEDGED</option><option>RESOLVED</option><option>SUPPRESSED</option></select>' +
      '    </div>' +
      '  </div>' +
      '  <div class="card-body" id="alertsTableBody">' +
      Components.tableHTML({
        columns: [
          { key: 'alert_id', label: 'ID' },
          { key: 'severity', label: 'Severidade', render: function (r) { return Components.severityBadgeHTML(r.severity); } },
          { key: 'status', label: 'Status', render: function (r) { return Components.statusBadgeHTML(r.status); } },
          { key: 'source', label: 'Origem' },
          { key: 'rule_id', label: 'Regra' },
          { key: 'target', label: 'Alvo' },
          { key: 'count', label: 'Count' },
          { key: 'last_seen', label: 'Última Ocorrência' }
        ],
        rows: []
      }) +
      '  </div>' +
      '</div>'
    );
  }
});