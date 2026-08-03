/**
 * EDY Shield Dashboard — Página IOC Manager (M4.1)
 * Gestão de Indicators of Compromise.
 */

Router.register('ioc', {
  title: 'IOC Manager',
  render: function () {
    return (
      '<div class="page-header page-header-compact">' +
      '  <div class="page-header-left">' +
      '    <h1>IOC Manager</h1>' +
      '    <p>Indicators of Compromise</p>' +
      '  </div>' +
      '  <button class="btn btn-sm btn-ghost">&#8682; Importar IOCs</button>' +
      '</div>' +
      '<div class="stat-grid stat-grid-compact" id="iocKpiGrid">' +
      Components.skeletonHTML('card', 4) +
      '</div>' +
      '<div class="card">' +
      '  <div class="card-header"><span class="card-title">Lista de IOCs</span>' +
      '    <input type="search" class="settings-input" placeholder="Filtrar IOCs..." style="max-width: 200px;">' +
      '  </div>' +
      '  <div class="card-body">' + Components.emptyStateHTML('\u9888', 'Nenhum IOC cadastrado', 'Importe uma lista de IOCs para come\u00e7ar.') + '</div>' +
      '</div>'
    );
  },
  onLoad: function () {
    // Encerra o skeleton imediatamente (sem API de IOCs no backend).
    // Garante: skeleton removido; resposta vazia -> KPIs zerados + empty state.
    var grid = document.getElementById('iocKpiGrid');
    if (grid) {
      grid.innerHTML = '' +
        Components.statCardHTML({ label: 'IOCs Totais', value: 0, severity: 'info', icon: '\u2637' }) +
        Components.statCardHTML({ label: 'IPs Maliciosos', value: 0, severity: 'high', icon: '\u21D1' }) +
        Components.statCardHTML({ label: 'Hashes', value: 0, severity: 'medium', icon: '\u25CF' }) +
        Components.statCardHTML({ label: 'Dom\u00ednios', value: 0, severity: 'low', icon: '\u2193' });
    }
  },
  onUnload: function () {
    if (Router.abortFetch) Router.abortFetch();
  }
});