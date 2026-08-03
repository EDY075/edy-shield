/**
 * EDY Shield Dashboard — Página Dashboard (M4.1)
 * Visão geral SOC: stats, alertas recentes, status do sistema.
 */

Router.register('dashboard', {
  title: 'Dashboard',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>Dashboard</h1>' +
      '    <p>Visão geral do EDY Shield em tempo real</p>' +
      '  </div>' +
      '  <button class="btn btn-primary" onclick="Dashboard.refresh()">Atualizar</button>' +
      '</div>' +
      '<div class="stat-grid">' +
      Components.statCardHTML({ label: 'Alertas Críticos', value: '—', severity: 'critical' }) +
      Components.statCardHTML({ label: 'Alertas Altos', value: '—', severity: 'high' }) +
      Components.statCardHTML({ label: 'Alertas Médios', value: '—', severity: 'medium' }) +
      Components.statCardHTML({ label: 'Total de Alertas', value: '—', severity: 'info' }) +
      '</div>' +
      '<div class="content-grid">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alertas Recentes</span>' +
      '      <button class="btn btn-sm btn-ghost" onclick="Router.navigate(\'alerts\')">Ver todos</button>' +
      '    </div>' +
      '    <div class="card-body" id="recentAlertsBody">' +
      Components.loadingHTML('Carregando alertas...') +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Status do Sistema</span></div>' +
      '    <div class="card-body">' +
      '      <div style="display: flex; flex-direction: column; gap: 12px;">' +
      '        <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-secondary);">API</span>' + Components.statusBadgeHTML('NEW') + '</div>' +
      '        <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-secondary);">WebSocket</span><span class="badge badge-status-suppressed">Offline</span></div>' +
      '        <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-secondary);">SQLite</span><span class="badge badge-status-resolved">OK</span></div>' +
      '        <div style="display: flex; justify-content: space-between;"><span style="color: var(--text-secondary);">Plugins</span><span class="badge badge-status-resolved">5 ativos</span></div>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '</div>'
    );
  }
});

var Dashboard = {
  refresh: function () {
    // Placeholder —_future: fetch alert stats from /api/alerts/stats
    Toast.info('Dashboard atualizado (demo)');
  }
};