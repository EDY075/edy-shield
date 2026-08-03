/**
 * EDY Shield Dashboard — Página Rules (M4.2)
 * Gerenciamento de regras do Alert Engine com dados reais via API.
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
      '  <button class="btn" onclick="RulesPage.refresh()">Atualizar</button>' +
      '</div>' +
      '<div class="card">' +
      '  <div class="card-header"><span class="card-title">Regras Ativas</span></div>' +
      '  <div class="card-body" id="rulesTableBody">' +
      Components.loadingHTML('Carregando regras...') +
      '  </div>' +
      '</div>'
    );
  },
  onLoad: function () {
    RulesPage.refresh();
  }
});

var RulesPage = {
  refresh: function () {
    EDY.api('/api/alerts/rules')
      .then(function (data) {
        var body = document.getElementById('rulesTableBody');
        if (!body) return;
        var rules = data.rules || [];
        if (rules.length === 0) {
          body.innerHTML = Components.emptyStateHTML('\u2699', 'Nenhuma regra ativa', 'As regras padr\u00e3o aparecer\u00e3o quando o motor de alertas for iniciado.');
          return;
        }
        body.innerHTML = Components.tableHTML({
          columns: [
            { key: 'rule_id', label: 'ID' },
            { key: 'name', label: 'Nome' },
            { key: 'source', label: 'Origem' },
            { key: 'operator', label: 'Operador' },
            { key: 'condition_value', label: 'Valor' },
            { key: 'target_severity', label: 'Severidade', render: function (r) { return Components.severityBadgeHTML(r.target_severity); } },
            { key: 'enabled', label: 'Ativo' }
          ],
          rows: rules.map(function (r) {
            return {
              rule_id: r.rule_id,
              name: r.name,
              source: r.source,
              operator: r.operator,
              condition_value: r.condition_value,
              target_severity: r.target_severity,
              enabled: r.enabled ? 'Sim' : 'N\u00e3o'
            };
          })
        });
      })
      .catch(function (err) {
        var body = document.getElementById('rulesTableBody');
        if (body) body.innerHTML = Components.errorStateHTML('Erro ao carregar', err.message);
      });
  }
};