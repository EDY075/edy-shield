/**
 * EDY Shield Dashboard — Página Assets (M4.1)
 * Inventário de assets monitorados.
 */

Router.register('assets', {
  title: 'Assets',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>Assets</h1>' +
      '    <p>Inventário de assets monitorados</p>' +
      '  </div>' +
      '  <button class="btn btn-primary">Adicionar Asset</button>' +
      '</div>' +
      '<div class="stat-grid">' +
      Components.statCardHTML({ label: 'Total Assets', value: '—', severity: 'info' }) +
      Components.statCardHTML({ label: 'Monitorados (FIM)', value: '—', severity: 'low' }) +
      Components.statCardHTML({ label: ' com Mudanças', value: '—', severity: 'high' }) +
      '</div>' +
      '<div class="card">' +
      '  <div class="card-header"><span class="card-title">Inventário</span></div>' +
      '  <div class="card-body">' + Components.emptyStateHTML('\u9112', 'Nenhum asset cadastrado', 'Adicione um asset para começar o monitoramento.') + '</div>' +
      '</div>'
    );
  }
});