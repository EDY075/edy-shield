/**
 * EDY Shield Dashboard — Página Rules (M4.1)
 * Gerenciamento de regras do Alert Engine.
 */

Router.register('rules', {
  title: 'Rules',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>Rules</h1>' +
      '    <p>Regras do motor de alertas</p>' +
      '  </div>' +
      '  <button class="btn btn-primary">Nova Regra</button>' +
      '</div>' +
      '<div class="card">' +
      '  <div class="card-header"><span class="card-title">Regras Ativas</span></div>' +
      '  <div class="card-body" id="rulesTableBody">' +
      Components.loadingHTML('Carregando regras...') +
      '  </div>' +
      '</div>'
    );
  }
});