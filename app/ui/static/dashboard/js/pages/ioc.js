/**
 * EDY Shield Dashboard — Página IOC Manager (M4.1)
 * Gestão de Indicators of Compromise.
 */

Router.register('ioc', {
  title: 'IOC Manager',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>IOC Manager</h1>' +
      '    <p>Indicators of Compromise</p>' +
      '  </div>' +
      '  <button class="btn btn-primary">Importar IOCs</button>' +
      '</div>' +
      '<div class="stat-grid">' +
      Components.statCardHTML({ label: 'IOCs Totais', value: '—', severity: 'info' }) +
      Components.statCardHTML({ label: 'IPs Maliciosos', value: '—', severity: 'high' }) +
      Components.statCardHTML({ label: 'Hashes', value: '—', severity: 'medium' }) +
      Components.statCardHTML({ label: 'Domínios', value: '—', severity: 'low' }) +
      '</div>' +
      '<div class="card">' +
      '  <div class="card-header"><span class="card-title">Lista de IOCs</span>' +
      '    <input type="search" class="topbar-search" placeholder="Filtrar IOCs..." style="max-width: 200px;">' +
      '  </div>' +
      '  <div class="card-body">' + Components.emptyStateHTML('\u9888', 'Nenhum IOC cadastrado', 'Importe uma lista de IOCs para começar.') + '</div>' +
      '</div>'
    );
  }
});