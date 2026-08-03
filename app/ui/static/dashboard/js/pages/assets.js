/**
 * EDY Shield Dashboard — Página Assets (M5.2 - Enterprise)
 * Inventário de assets monitorados.
 * Mesmo padrão visual Enterprise: header compacto, skeleton loading,
 * KPI cards, tabela padronizada e empty state profissional.
 * Sem alterações de API/backend — somente UI.
 */

Router.register('assets', {
  title: 'Assets',
  render: function () {
    return (
      '<div class="page-header page-header-compact">' +
      '  <div class="page-header-left">' +
      '    <h1>Assets</h1>' +
      '    <p>Invent\u00e1rio de assets monitorados</p>' +
      '  </div>' +
      '  <button class="btn btn-sm btn-ghost">&#43; Adicionar Asset</button>' +
      '</div>' +
      '<div class="stat-grid stat-grid-compact" id="assetsKpiGrid">' +
      Components.skeletonHTML('card', 4) +
      '</div>' +
      '<div class="card">' +
      '  <div class="card-header">' +
      '    <span class="card-title">Invent\u00e1rio</span>' +
      '    <input type="search" class="settings-input" placeholder="Filtrar assets..." style="max-width: 200px;">' +
      '  </div>' +
      '  <div class="card-body" style="padding: 0;">' +
      '    <div class="alert-table-wrap">' +
      '      <table class="alert-table">' +
      '        <thead><tr>' +
      '          <th>Hostname</th>' +
      '          <th>IP</th>' +
      '          <th>Sistema</th>' +
      '          <th>\u00daltimo Seen</th>' +
      '          <th>Status</th>' +
      '          <th>Risco</th>' +
      '          <th>Tags</th>' +
      '        </tr></thead>' +
      '        <tbody id="assetsTableBody">' +
      '          <tr><td colspan="7" style="padding: 16px;">' + Components.skeletonHTML('bar', 5) + '</td></tr>' +
      '        </tbody>' +
      '      </table>' +
      '    </div>' +
      '  </div>' +
      '</div>'
    );
  },
  onLoad: function () {
    AssetsPage._renderEmpty();
  }
});

var AssetsPage = {
  _renderEmpty: function () {
    // Sem API de assets no backend — estado vazio profissional com KPIs zerados.
    var grid = document.getElementById('assetsKpiGrid');
    if (grid) {
      grid.innerHTML = '' +
        Components.statCardHTML({ label: 'Total Assets', value: 0, severity: 'info', icon: '\u25A2' }) +
        Components.statCardHTML({ label: 'Monitorados (FIM)', value: 0, severity: 'low', icon: '\u25A3' }) +
        Components.statCardHTML({ label: 'Com Mudan\u00e7as', value: 0, severity: 'high', icon: '\u21D1' }) +
        Components.statCardHTML({ label: 'Risco Cr\u00edtico', value: 0, severity: 'critical', icon: '\u26A0' });
    }
    var body = document.getElementById('assetsTableBody');
    if (body) {
      body.innerHTML = '<tr><td colspan="7">' +
        Components.emptyStateHTML('\u25A2', 'Nenhum asset cadastrado',
          'Adicione um asset para come\u00e7ar o monitoramento.') +
        '</td></tr>';
    }
  }
};
