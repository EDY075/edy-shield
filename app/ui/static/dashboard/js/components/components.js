/**
 * EDY Shield Dashboard — Componentes Reutilizáveis (M4.1)
 *
 * Funções factory para criar elementos DOM padronizados:
 * loading, emptyState, errorState, statCard, table, badge.
 */

var Components = (function () {
  'use strict';

  /**
   * Retorna o HTML do estado de loading (spinner + texto).
   * @param {string} msg - Mensagem opcional de loading.
   * @returns {string} HTML do estado de loading.
   */
  function loadingHTML(msg) {
    msg = msg || 'Carregando dados...';
    return (
      '<div class="loading-container">' +
      '  <div>' +
      '    <div class="spinner"></div>' +
      '    <div class="loading-text">' + _escape(msg) + '</div>' +
      '  </div>' +
      '</div>'
    );
  }

  /**
   * Retorna o HTML do estado vazio (empty state).
   * @param {string} icon - Ícone Unicode.
   * @param {string} title - Título do estado vazio.
   * @param {string} description - Descrição do estado vazio.
   * @returns {string} HTML do empty state.
   */
  function emptyStateHTML(icon, title, description) {
    return (
      '<div class="empty-state">' +
      '  <div class="empty-state-icon">' + (icon || '\u2205') + '</div>' +
      '  <div class="empty-state-title">' + _escape(title || 'Nada por aqui') + '</div>' +
      '  <div class="empty-state-description">' + _escape(description || 'Nenhum dado disponível.') + '</div>' +
      '</div>'
    );
  }

  /**
   * Retorna o HTML do estado de erro.
   * @param {string} title - Título do erro.
   * @param {string} description - Descrição do erro.
   * @returns {string} HTML do error state.
   */
  function errorStateHTML(title, description) {
    return (
      '<div class="error-state">' +
      '  <div class="error-state-icon">' + '\u26A0' + '</div>' +
      '  <div class="error-state-title">' + _escape(title || 'Erro ao carregar') + '</div>' +
      '  <div class="error-state-description">' + _escape(description || 'Tente novamente mais tarde.') + '</div>' +
      '</div>'
    );
  }

  /**
   * Retorna o HTML de um stat card (card de métrica).
   * @param {object} opts - { label, value, severity, trend }
   * @returns {string} HTML do stat card.
   */
  function statCardHTML(opts) {
    var sev = opts.severity || 'info';
    var trend = '';
    if (opts.trend) {
      var trendClass = opts.trendDirection === 'up' ? 'up' : 'down';
      var trendIcon = trendClass === 'up' ? '\u2191' : '\u2193';
      trend =
        '<div class="stat-card-trend ' + trendClass + '">' +
        trendIcon + ' ' + _escape(opts.trend) +
        '</div>';
    }
    return (
      '<div class="stat-card severity-' + sev + '">' +
      '  <div class="stat-card-label">' + _escape(opts.label || '') + '</div>' +
      '  <div class="stat-card-value">' + _escape(String(opts.value || 0)) + '</div>' +
      trend +
      '</div>'
    );
  }

  /**
   * Retorna o HTML de um badge de severidade.
   * @param {string} severity - INFO|LOW|MEDIUM|HIGH|CRITICAL
   * @returns {string} HTML do badge.
   */
  function severityBadgeHTML(severity) {
    var sev = (severity || 'info').toLowerCase();
    return '<span class="badge badge-' + sev + '">' + _escape(severity || 'INFO') + '</span>';
  }

  /**
   * Retorna o HTML de um badge de status.
   * @param {string} status - NEW|ACKNOWLEDGED|RESOLVED|SUPPRESSED
   * @returns {string} HTML do badge.
   */
  function statusBadgeHTML(status) {
    var s = (status || 'NEW').toUpperCase();
    var cls = 'badge-status-new';
    if (s === 'ACKNOWLEDGED') cls = 'badge-status-ack';
    else if (s === 'RESOLVED') cls = 'badge-status-resolved';
    else if (s === 'SUPPRESSED') cls = 'badge-status-suppressed';
    return '<span class="badge ' + cls + '">' + _escape(s) + '</span>';
  }

  /**
   * Retorna o HTML de uma tabela de dados (placeholder para DataTable).
   * @param {object} opts - { columns: [], rows: [] }
   * @returns {string} HTML da tabela.
   */
  function tableHTML(opts) {
    var cols = opts.columns || [];
    var rows = opts.rows || [];
    if (cols.length === 0) return emptyStateHTML('\u2261', 'Sem colunas', '');

    var thead = cols.map(function (c) {
      return '<th>' + _escape(c.label || c.key || '') + '</th>';
    }).join('');

    var tbody = '';
    if (rows.length === 0) {
      tbody = '<tr><td colspan="' + cols.length + '">' +
        emptyStateHTML('\u2205', 'Nenhum registro', 'Nenhum dado para exibir.') +
        '</td></tr>';
    } else {
      tbody = rows.map(function (row) {
        var cells = cols.map(function (c) {
          var val = row[c.key] !== undefined ? row[c.key] : '';
          return '<td>' + (c.render ? c.render(row) : _escape(String(val))) + '</td>';
        }).join('');
        return '<tr>' + cells + '</tr>';
      }).join('');
    }

    return (
      '<div class="table-container">' +
      '  <table class="data-table">' +
      '    <thead><tr>' + thead + '</tr></thead>' +
      '    <tbody>' + tbody + '</tbody>' +
      '  </table>' +
      '</div>'
    );
  }

  /**
   * Escapa texto para prevenir XSS em innerHTML.
   * @param {string} text - Texto a escapar.
   * @returns {string} Texto escapado.
   */
  function _escape(text) {
    if (text === null || text === undefined) return '';
    var div = document.createElement('div');
    div.textContent = String(text);
    return div.innerHTML;
  }

  return {
    loadingHTML: loadingHTML,
    emptyStateHTML: emptyStateHTML,
    errorStateHTML: errorStateHTML,
    statCardHTML: statCardHTML,
    severityBadgeHTML: severityBadgeHTML,
    statusBadgeHTML: statusBadgeHTML,
    tableHTML: tableHTML,
    escape: _escape
  };
})();