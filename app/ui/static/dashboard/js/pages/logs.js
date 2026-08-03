/**
 * EDY Shield Dashboard — Página Logs (M4.1)
 * Visualizador de logs do sistema.
 */

Router.register('logs', {
  title: 'Logs',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>Logs</h1>' +
      '    <p>Visualizador de logs do sistema</p>' +
      '  </div>' +
      '  <div style="display: flex; gap: 8px;">' +
      '    <button class="btn">Exportar</button>' +
      '    <button class="btn">Limpar Filtros</button>' +
      '  </div>' +
      '</div>' +
      '<div class="card">' +
      '  <div class="card-header">' +
      '    <span class="card-title">Eventos de Log</span>' +
      '    <select class="btn"><option>Todos os n\u00edveis</option><option>INFO</option><option>WARNING</option><option>ERROR</option></select>' +
      '  </div>' +
      '  <div class="card-body" style="background: var(--bg-base); border-radius: 8px; font-family: var(--font-mono); font-size: 12px; padding: 12px; max-height: 500px; overflow-y: auto;">' +
      Components.emptyStateHTML('\u9776', 'Nenhum log dispon\u00edvel', 'Os logs do sistema aparecer\u00e3o aqui.') +
      '  </div>' +
      '</div>'
    );
  }
});