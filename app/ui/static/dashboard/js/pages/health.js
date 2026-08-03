/**
 * EDY Shield Dashboard — Página System Health (M4.1)
 * Monitor de saúde do sistema.
 */

Router.register('health', {
  title: 'System Health',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>System Health</h1>' +
      '    <p>Monitor de saúde e performance</p>' +
      '  </div>' +
      '  <button class="btn">Executar Diagnóstico</button>' +
      '</div>' +
      '<div class="stat-grid">' +
      Components.statCardHTML({ label: 'CPU', value: '—%', severity: 'low' }) +
      Components.statCardHTML({ label: 'Memória', value: '—MB', severity: 'low' }) +
      Components.statCardHTML({ label: 'SQLite (WAL)', value: 'OK', severity: 'info' }) +
      Components.statCardHTML({ label: 'Uptime', value: '—', severity: 'info' }) +
      '</div>' +
      '<div class="content-grid">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Status dos Componentes</span></div>' +
      '    <div class="card-body">' +
      '      <div style="display: flex; flex-direction: column; gap: 12px;">' +
      '        <div style="display: flex; justify-content: space-between;"><span>API REST</span>' + Components.statusBadgeHTML('RESOLVED') + '</div>' +
      '        <div style="display: flex; justify-content: space-between;"><span>SQLite</span>' + Components.statusBadgeHTML('RESOLVED') + '</div>' +
      '        <div style="display: flex; justify-content: space-between;"><span>Alert Engine</span>' + Components.statusBadgeHTML('RESOLVED') + '</div>' +
      '        <div style="display: flex; justify-content: space-between;"><span>Plugin Manager</span>' + Components.statusBadgeHTML('RESOLVED') + '</div>' +
      '        <div style="display: flex; justify-content: space-between;"><span>WebSocket</span>' + Components.statusBadgeHTML('SUPPRESSED') + '</div>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Métricas</span></div>' +
      '    <div class="card-body">' + Components.loadingHTML('Carregando métricas...') + '</div>' +
      '  </div>' +
      '</div>'
    );
  }
});