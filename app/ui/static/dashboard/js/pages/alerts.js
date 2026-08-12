/**
 * EDY Shield Dashboard — Alert Center (M4.3)
 *
 * Central operacional de alertas com:
 * - Tabela profissional com paginação, ordenação e pesquisa instantânea
 * - Filtros combinados por severidade, status, origem, regra e período
 * - Seleção múltipla com checkboxes e ações em lote (ACK, Resolve, Suppress)
 * - Painel lateral deslizante (detalhes, fingerprint, timeline, histórico, comentários)
 * - Ações individuais no painel lateral (ACK, Resolve, Suppress, Reopen)
 * - Preservação de estado/filtros durante auto-refresh
 */

Router.register('alerts', {
  title: 'Alert Center',
  render: function () {
    return (
      '<div class="page-header page-header-compact">' +
      '  <div class="page-header-left">' +
      '    <h1>Alert Center</h1>' +
      '    <p>Central de triagem e resposta a incidentes</p>' +
      '  </div>' +
      '  <div style="display: flex; gap: 8px; align-items: center;">' +
      '    <button class="btn btn-sm btn-ghost" onclick="AlertsPage.refresh()">&#10227; Atualizar</button>' +
      '    <button class="btn btn-sm btn-ghost">&#8681; Exportar</button>' +
      '    <button class="btn btn-sm btn-ghost">A\u00e7\u00f5es em lote</button>' +
      '  </div>' +
      '</div>' +

      // KPI Grid — Severidade com mini-barras (referência)
      '<div class="stat-grid stat-grid-5" id="alertsKpiGrid">' +
      Components.skeletonHTML('card', 5) +
      '</div>' +

      // Batch Bar (visível, desabilitada quando 0 — referência)
      '<div class="batch-bar" id="batchBar" style="display: flex; opacity: 0.5; pointer-events: none;">' +
      '  <span class="batch-bar-count"><span id="selectedCount">0</span> selecionados</span>' +
      '  <div class="batch-bar-actions">' +
      '    <button class="btn btn-sm" onclick="AlertsPage.batchAction(\'ack\')">&#10003; Reconhecer Em Lote</button>' +
      '    <button class="btn btn-sm btn-primary" onclick="AlertsPage.batchAction(\'resolve\')">&#10004; Resolver Em Lote</button>' +
      '    <button class="btn btn-sm" onclick="AlertsPage.batchAction(\'suppress\')">&#128683; Suprimir Em Lote</button>' +
      '    <button class="btn btn-sm btn-ghost" onclick="AlertsPage.clearSelection()">Cancelar</button>' +
      '  </div>' +
      '</div>' +

      // Toolbar de Filtros e Busca — linha única (M4.4.5)
      '<div class="card card-alerts">' +
      '  <div class="alert-center-toolbar" style="margin: 0; padding: 12px;">' +
      '    <input type="search" id="alertSearchInput" placeholder="Pesquisar alerta, asset..." style="width: 240px;" oninput="AlertsPage.onSearchInput()">' +
      '    <select id="filterSeverity" onchange="AlertsPage.onFilterChange()">' +
      '      <option value="">Severidade</option>' +
      '      <option value="CRITICAL">CRITICAL</option>' +
      '      <option value="HIGH">HIGH</option>' +
      '      <option value="MEDIUM">MEDIUM</option>' +
      '      <option value="LOW">LOW</option>' +
      '      <option value="INFO">INFO</option>' +
      '    </select>' +
      '    <select id="filterStatus" onchange="AlertsPage.onFilterChange()">' +
      '      <option value="">Status</option>' +
      '      <option value="NEW">NEW</option>' +
      '      <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>' +
      '      <option value="RESOLVED">RESOLVED</option>' +
      '      <option value="SUPPRESSED">SUPPRESSED</option>' +
      '    </select>' +
      '    <select id="filterSource" onchange="AlertsPage.onFilterChange()">' +
      '      <option value="">Origem</option>' +
      '      <option value="fim">FIM</option>' +
      '      <option value="string_analyzer">String Analyzer</option>' +
      '      <option value="entropy_analyzer">Entropy Analyzer</option>' +
      '      <option value="log_analyzer">Log Analyzer</option>' +
      '    </select>' +
      '    <select id="filterPeriod" onchange="AlertsPage.onFilterChange()">' +
      '      <option value="">Per\u00edodo</option>' +
      '      <option value="1h">\u00daltima 1 hora</option>' +
      '      <option value="24h">\u00daltimas 24 horas</option>' +
      '      <option value="7d">\u00daltimos 7 dias</option>' +
      '      <option value="30d">\u00daltimos 30 dias</option>' +
      '    </select>' +
      '  </div>' +

      // Contador de alertas encontrados (referência)
      '<div class="alert-results-count" id="alertsCountLine" style="display: none;"></div>' +

      // Tabela de Alertas
      '  <div class="card-body" style="padding: 0;">' +
      '    <div class="alert-table-wrap">' +
      '      <table class="alert-table" id="alertsTable">' +
      '        <thead>' +
      '          <tr>' +
      '            <th class="col-checkbox"><input type="checkbox" id="selectAllCheckbox" onchange="AlertsPage.toggleSelectAll()"></th>' +
      '            <th class="col-sev" onclick="AlertsPage.sort(\'severity\')">Severidade</th>' +
      '            <th class="col-status" onclick="AlertsPage.sort(\'status\')">Status</th>' +
      '            <th onclick="AlertsPage.sort(\'title\')">T\u00edtulo</th>' +
      '            <th onclick="AlertsPage.sort(\'rule_id\')">Regra</th>' +
      '            <th onclick="AlertsPage.sort(\'source\')">Origem</th>' +
      '            <th onclick="AlertsPage.sort(\'target\')">Asset / Alvo</th>' +
      '            <th class="col-count" onclick="AlertsPage.sort(\'count\')">Count</th>' +
      '            <th class="col-time" onclick="AlertsPage.sort(\'last_seen_at\')">\u00daltima Ocorr\u00eancia</th>' +
      '          </tr>' +
      '        </thead>' +
      '        <tbody id="alertsTableBody">' +
      '          <tr><td colspan="9" style="text-align: center; padding: 32px;">' + Components.loadingHTML('Carregando alertas...') + '</td></tr>' +
      '        </tbody>' +
      '      </table>' +
      '    </div>' +
      '  </div>' +

      // Paginação
      '  <div class="alert-pagination" style="padding: 16px;">' +
      '    <span class="alert-pagination-info" id="paginationInfo">Mostrando 0-0 de 0 alertas</span>' +
      '    <div class="alert-pagination-controls" id="paginationControls"></div>' +
      '  </div>' +
      '</div>' +

      // Backdrop do Painel Lateral
      '<div class="alert-side-panel-backdrop" id="sidePanelBackdrop" onclick="AlertsPage.closePanel()"></div>' +

      // Detalhe operacional da mudan\u00e7a (Product Redesign V1 / Sprint A3)
      '<aside class="alert-side-panel event-detail-panel" id="alertSidePanel" aria-label="Detalhe da mudan\u00e7a">' +
      '  <div class="alert-side-panel-header">' +
      '    <div class="alert-side-panel-title" id="panelTitle">Detalhes do Alerta</div>' +
      '    <span class="alert-side-panel-meta" id="panelFingerprint"></span>' +
      '    <button class="alert-side-panel-close" onclick="AlertsPage.closePanel()" aria-label="Fechar detalhes do alerta">&times;</button>' +
      '  </div>' +
      '  <div class="alert-side-panel-body" id="panelBody">' +
      '    <p style="color: var(--text-tertiary);">Selecione um alerta para investigar.</p>' +
      '  </div>' +
      '</aside>'
    );
  },

  onLoad: function () {
    AlertsPage._refreshHandler = function () { AlertsPage.refresh(true); };
    document.addEventListener('edy-refresh', AlertsPage._refreshHandler);
    AlertsPage.refresh();
  },

  onUnload: function () {
    if (AlertsPage._refreshHandler) {
      document.removeEventListener('edy-refresh', AlertsPage._refreshHandler);
      AlertsPage._refreshHandler = null;
    }
    if (Router.abortFetch) Router.abortFetch();
  }
});

var AlertsPage = (function () {
  'use strict';

  var state = {
    alerts: [],
    filteredAlerts: [],
    selectedIds: new Set(),
    activeAlert: null,
    sortField: 'last_seen_at',
    sortAsc: false,
    page: 1,
    pageSize: 15,
    searchDebounce: null,
    siemContext: null,
    hostname: null
  };

  function refresh(silent) {
    _loadStats();
    _loadAlerts(silent);
  }

  function _loadStats() {
    EDY.api('/api/alerts/stats')
      .then(function (stats) {
        var sev = stats.by_severity || {};
        var grid = document.getElementById('alertsKpiGrid');
        if (!grid) return;
        var defs = [
          { label: 'Cr\u00edticos', key: 'CRITICAL', sev: 'critical', icon: '\u26A0' },
          { label: 'Altos', key: 'HIGH', sev: 'high', icon: '\u21D1' },
          { label: 'M\u00e9dios', key: 'MEDIUM', sev: 'medium', icon: '\u25CF' },
          { label: 'Baixos', key: 'LOW', sev: 'low', icon: '\u2193' },
          { label: 'Resolvidos', key: 'RESOLVED', sev: 'info', icon: '\u2713' }
        ];
        var maxVal = Math.max(1, Math.max.apply(null, defs.map(function (d) { return sev[d.key] || 0; })));
        grid.innerHTML = defs.map(function (d) {
          var val = sev[d.key] || 0;
          var pct = Math.round(val / maxVal * 100);
          return '<div class="stat-card severity-' + d.sev + '">' +
            '<div class="stat-card-top">' +
            '  <div class="stat-card-icon severity-' + d.sev + '">' + d.icon + '</div>' +
            '  <div class="stat-card-label">' + d.label + '</div>' +
            '</div>' +
            '<div class="stat-card-value">' + val + '</div>' +
            '<div class="stat-card-minibar"><div class="stat-card-minibar-fill sev-' + d.sev + '" style="width: ' + pct + '%;"></div></div>' +
            '</div>';
        }).join('');
      })
      .catch(function () {});
  }

  function _loadAlerts(silent) {
    var query = _buildQueryString();
    if (!silent) {
      var body = document.getElementById('alertsTableBody');
      if (body) {
        body.innerHTML = '<tr><td colspan="9" style="padding: 16px;">' +
          Components.skeletonHTML('bar', 5) + '</td></tr>';
      }
    }

    EDY.api('/api/alerts' + query)
      .then(function (data) {
        state.alerts = data.alerts || [];
        _applyClientFiltersAndSort();
        _renderTable();
        _renderPagination();
        _updateBatchBar();
        _openPendingAlert();
      })
      .catch(function (err) {
        if (err.name === 'AbortError') return;
        var body = document.getElementById('alertsTableBody');
        if (body) {
          body.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 32px;">' +
            Components.errorStateHTML('Erro ao carregar', err.message) + '</td></tr>';
        }
      });
  }

  function _buildQueryString() {
    var sev = _val('filterSeverity');
    var status = _val('filterStatus');
    var source = _val('filterSource');
    var period = _val('filterPeriod');
    var q = _val('alertSearchInput');

    var params = ['limit=200'];
    if (sev) params.push('severity=' + encodeURIComponent(sev));
    if (status) params.push('status=' + encodeURIComponent(status));
    if (source) params.push('source=' + encodeURIComponent(source));
    if (q) params.push('q=' + encodeURIComponent(q));

    if (period) {
      var since = _calculateSince(period);
      if (since) params.push('since=' + encodeURIComponent(since));
    }

    return '?' + params.join('&');
  }

  function _calculateSince(period) {
    var now = new Date();
    var ms = 0;
    if (period === '1h') ms = 3600 * 1000;
    else if (period === '24h') ms = 86400 * 1000;
    else if (period === '7d') ms = 7 * 86400 * 1000;
    else if (period === '30d') ms = 30 * 86400 * 1000;
    if (!ms) return null;
    return new Date(now.getTime() - ms).toISOString();
  }

  function _val(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : '';
  }

  function _applyClientFiltersAndSort() {
    var list = state.alerts.slice();

    // Ordenação
    var field = state.sortField;
    var asc = state.sortAsc ? 1 : -1;
    var sevRank = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0 };

    list.sort(function (a, b) {
      var valA = a[field];
      var valB = b[field];

      if (field === 'severity') {
        valA = sevRank[a.severity] !== undefined ? sevRank[a.severity] : -1;
        valB = sevRank[b.severity] !== undefined ? sevRank[b.severity] : -1;
      }

      if (valA < valB) return -1 * asc;
      if (valA > valB) return 1 * asc;
      return 0;
    });

    state.filteredAlerts = list;
  }

  function _renderTable() {
    var body = document.getElementById('alertsTableBody');
    if (!body) return;

    var list = state.filteredAlerts;
    if (list.length === 0) {
      body.innerHTML = '<tr><td colspan="9" style="text-align: center; padding: 32px;">' +
        Components.emptyStateHTML('\u2205', 'Nenhum alerta encontrado', 'Ajuste os filtros ou a pesquisa.') +
        '</td></tr>';
      return;
    }

    // Paginação slices
    var start = (state.page - 1) * state.pageSize;
    var pageList = list.slice(start, start + state.pageSize);

    var html = pageList.map(function (a) {
      var isChecked = state.selectedIds.has(a.alert_id) ? 'checked' : '';
      var isSelectedRow = state.selectedIds.has(a.alert_id) ? 'selected' : '';
      var rowClass = (a.severity === 'CRITICAL' ? 'alert-row-critical ' : '') + isSelectedRow;
      var timeStr = a.last_seen_at ? a.last_seen_at.slice(0, 19).replace('T', ' ') : '-';
      var safeAlertId = Components.escape(a.alert_id || '');

      return '' +
        '<tr class="' + rowClass + '" data-id="' + safeAlertId + '" onclick="AlertsPage.onRowClick(event, this.dataset.id)">' +
        '  <td class="col-checkbox" onclick="event.stopPropagation()">' +
        '    <input type="checkbox" class="row-checkbox" value="' + safeAlertId + '" ' + isChecked + ' onchange="AlertsPage.toggleSelect(this.value)">' +
        '  </td>' +
        '  <td class="col-sev">' + Components.severityBadgeHTML(a.severity) + '</td>' +
        '  <td class="col-status">' + Components.statusBadgeHTML(a.status) + '</td>' +
        '  <td><strong>' + Components.escape(a.title || a.rule_id || '-') + '</strong></td>' +
        '  <td><span class="badge badge-status-ack">' + Components.escape(a.rule_id || '-') + '</span></td>' +
        '  <td>' + Components.escape(a.source || '-') + '</td>' +
        '  <td style="max-width: 180px; overflow: hidden; text-overflow: ellipsis;">' + Components.escape(a.target || '-') + '</td>' +
        '  <td class="col-count"><strong>' + Components.escape(String(a.count || 1)) + '</strong></td>' +
        '  <td class="col-time">' + Components.escape(timeStr) + '</td>' +
        '</tr>';
    }).join('');

    body.innerHTML = html;
  }

  function _renderPagination() {
    var total = state.filteredAlerts.length;
    var info = document.getElementById('paginationInfo');
    var controls = document.getElementById('paginationControls');
    var countLine = document.getElementById('alertsCountLine');
    if (countLine) {
      countLine.style.display = 'flex';
      countLine.textContent = total + (total === 1 ? ' alerta encontrado' : ' alertas encontrados');
    }
    if (!info || !controls) return;

    if (total === 0) {
      info.textContent = 'Mostrando 0 de 0 alertas';
      controls.innerHTML = '';
      return;
    }

    var totalPages = Math.ceil(total / state.pageSize);
    if (state.page > totalPages) state.page = totalPages;

    var start = (state.page - 1) * state.pageSize + 1;
    var end = Math.min(state.page * state.pageSize, total);
    info.textContent = 'Mostrando ' + start + '-' + end + ' de ' + total + ' alertas';

    var html = '';
    html += '<button class="alert-pagination-btn" onclick="AlertsPage.goToPage(' + (state.page - 1) + ')" ' + (state.page === 1 ? 'disabled' : '') + '>&laquo;</button>';

    for (var p = 1; p <= totalPages; p++) {
      if (p === 1 || p === totalPages || Math.abs(p - state.page) <= 2) {
        html += '<button class="alert-pagination-btn ' + (p === state.page ? 'active' : '') + '" onclick="AlertsPage.goToPage(' + p + ')">' + p + '</button>';
      } else if (p === 2 || p === totalPages - 1) {
        html += '<span style="color: var(--text-tertiary); padding: 0 4px;">...</span>';
      }
    }

    html += '<button class="alert-pagination-btn" onclick="AlertsPage.goToPage(' + (state.page + 1) + ')" ' + (state.page === totalPages ? 'disabled' : '') + '>&raquo;</button>';
    controls.innerHTML = html;
  }

  function goToPage(p) {
    var totalPages = Math.ceil(state.filteredAlerts.length / state.pageSize);
    if (p >= 1 && p <= totalPages) {
      state.page = p;
      _renderTable();
      _renderPagination();
    }
  }

  function sort(field) {
    if (state.sortField === field) {
      state.sortAsc = !state.sortAsc;
    } else {
      state.sortField = field;
      state.sortAsc = true;
    }
    _applyClientFiltersAndSort();
    _renderTable();
  }

  function onFilterChange() {
    state.page = 1;
    _loadAlerts();
  }

  function onSearchInput() {
    if (state.searchDebounce) clearTimeout(state.searchDebounce);
    state.searchDebounce = setTimeout(function () {
      state.page = 1;
      _loadAlerts();
    }, 300);
  }

  // --- Seleção Múltipla & Batch Bar ---
  function toggleSelect(id) {
    if (state.selectedIds.has(id)) {
      state.selectedIds.delete(id);
    } else {
      state.selectedIds.add(id);
    }
    _updateBatchBar();
    _renderTable();
  }

  function toggleSelectAll() {
    var chk = document.getElementById('selectAllCheckbox');
    var start = (state.page - 1) * state.pageSize;
    var pageList = state.filteredAlerts.slice(start, start + state.pageSize);

    if (chk && chk.checked) {
      pageList.forEach(function (a) { state.selectedIds.add(a.alert_id); });
    } else {
      pageList.forEach(function (a) { state.selectedIds.delete(a.alert_id); });
    }
    _updateBatchBar();
    _renderTable();
  }

  function clearSelection() {
    state.selectedIds.clear();
    var chk = document.getElementById('selectAllCheckbox');
    if (chk) chk.checked = false;
    _updateBatchBar();
    _renderTable();
  }
  function _updateBatchBar() {
    var bar = document.getElementById('batchBar');
    var countEl = document.getElementById('selectedCount');
    var count = state.selectedIds.size;
    if (!bar) return;

    if (count > 0) {
      bar.style.display = 'flex';
      if (countEl) countEl.textContent = count;
    } else {
      bar.style.display = 'flex';
      bar.style.opacity = '0.5';
      bar.style.pointerEvents = 'none';
      if (countEl) countEl.textContent = '0';
    }
  }

  function batchAction(action) {
    var ids = Array.from(state.selectedIds);
    if (ids.length === 0) return;

    var actionNames = { ack: 'reconhecer', resolve: 'resolver', suppress: 'suprimir' };
    var label = actionNames[action] || action;

    if (!confirm('Deseja ' + label + ' ' + ids.length + ' alerta(s)?')) return;

    EDY.apiPost('/api/alerts/batch', {
      alert_ids: ids,
      action: action,
      by: 'analyst',
      note: 'A\u00e7\u00e3o em lote no Alert Center'
    })
    .then(function (res) {
      var successCount = (res.success || []).length;
      Toast.success(successCount + ' alerta(s) alterado(s) com sucesso.');
      clearSelection();
      refresh();
    })
    .catch(function (err) {
      Toast.error('Erro na a\u00e7\u00e3o em lote: ' + err.message);
    });
  }

  // --- Painel Lateral (Slide Panel) ---
  function onRowClick(event, id) {
    var alert = state.alerts.find(function (a) { return a.alert_id === id; });
    if (!alert) return;
    openPanel(alert);
  }

  function openPanel(alert) {
    state.activeAlert = alert;
    state.siemContext = {
      delivery_state: 'loading',
      label: 'Consultando entrega ao SIEM',
      description: 'Validando o estado real do evento na fila local.'
    };
    state.hostname = _detailValue(alert.details || {}, ['hostname', 'host', 'asset_hostname']) || null;
    var panel = document.getElementById('alertSidePanel');
    var backdrop = document.getElementById('sidePanelBackdrop');
    var title = document.getElementById('panelTitle');
    var fp = document.getElementById('panelFingerprint');

    if (!panel) return;

    if (title) {
      title.innerHTML = Components.severityBadgeHTML(alert.severity) +
        Components.statusBadgeHTML(alert.status) +
        ' <span class="event-detail-title-copy">' + Components.escape(_changeLabel(alert)) + '</span>';
    }
    if (fp) {
      fp.textContent = _filePath(alert) + '  ·  ' + _formatDate(alert.last_seen_at);
      fp.title = 'Alerta: ' + (alert.alert_id || '') + ' | Fingerprint: ' + (alert.fingerprint || '');
    }

    panel.classList.add('open');
    if (backdrop) backdrop.classList.add('open');
    _renderDecisionWorkspace();
    _loadSiemInvestigation(alert.alert_id);
    _loadEndpointContext(alert.alert_id);
  }

  function _openPendingAlert() {
    var alertId = sessionStorage.getItem('edy-shield-open-alert');
    if (!alertId) return;
    var alert = state.alerts.find(function (item) { return item.alert_id === alertId; });
    if (!alert) return;
    sessionStorage.removeItem('edy-shield-open-alert');
    openPanel(alert);
  }

  function _loadSiemInvestigation(alertId) {
    EDY.api('/api/integrations/edy-siem/alerts/' + encodeURIComponent(alertId))
      .then(function (context) {
        if (!state.activeAlert || state.activeAlert.alert_id !== alertId) return;
        state.siemContext = context;
        _renderDecisionWorkspace();
      })
      .catch(function () {
        if (!state.activeAlert || state.activeAlert.alert_id !== alertId) return;
        state.siemContext = {
          delivery_state: 'temporary_failure',
          label: 'Falha tempor\u00e1ria',
          description: 'N\u00e3o foi poss\u00edvel consultar a entrega agora.',
          can_investigate: false
        };
        _renderDecisionWorkspace();
      });
  }

  function _loadEndpointContext(alertId) {
    EDY.api('/api/health')
      .then(function (health) {
        if (!state.activeAlert || state.activeAlert.alert_id !== alertId) return;
        if (!state.hostname && typeof health.hostname === 'string' && health.hostname.trim()) {
          state.hostname = health.hostname;
          _renderDecisionWorkspace();
        }
      })
      .catch(function () {
        // O detalhe continua utiliz\u00e1vel sem o hostname do endpoint.
      });
  }

  function openSiemInvestigation() {
    var context = state.siemContext;
    if (!context || !context.can_investigate || typeof context.investigation_url !== 'string') return;
    if (!/^https?:\/\//i.test(context.investigation_url)) return;
    window.open(context.investigation_url, '_blank', 'noopener,noreferrer');
  }

  function _renderDecisionWorkspace() {
    var body = document.getElementById('panelBody');
    var a = state.activeAlert;
    if (!body || !a) return;
    var d = a.details || {};
    var hostname = state.hostname || 'N\u00e3o informado';
    var sourceLabel = a.source === 'fim' ? 'File Integrity Monitor' : (a.source || 'Evento local');

    body.innerHTML = '<div class="event-detail-flow">' +
      '<section class="event-change-summary" aria-labelledby="eventChangeHeading">' +
      '  <div class="event-section-heading"><span class="event-step-index">01</span><div><span class="page-eyebrow">Mudan\u00e7a</span><h2 id="eventChangeHeading">' + Components.escape(_changeLabel(a)) + '</h2></div></div>' +
      '  <p class="event-change-description">' + Components.escape(a.description || 'Evento registrado pelo EDY Shield.') + '</p>' +
      '  <dl class="event-header-facts">' +
      _detailFact('Severidade', a.severity || 'N\u00e3o informada') +
      _detailFact('Hostname', hostname, true) +
      _detailFact('Arquivo afetado', _filePath(a), true) +
      _detailFact('Timestamp', _formatDate(a.last_seen_at)) +
      _detailFact('Origem', sourceLabel) +
      _detailFact('Estado local', _statusLabel(a.status)) +
      '  </dl>' +
      _siemStatusHTML() +
      '</section>' +

      '<section class="event-flow-section event-evidence-section" aria-labelledby="eventEvidenceHeading">' +
      '  <div class="event-section-heading"><span class="event-step-index">02</span><div><span class="page-eyebrow">Evid\u00eancia</span><h2 id="eventEvidenceHeading">O que mudou</h2></div></div>' +
      '  <div class="event-primary-path"><span>File path</span><code>' + Components.escape(_filePath(a)) + '</code></div>' +
      _hashComparisonHTML(d) +
      _baselineContextHTML(a) +
      '  <details class="event-technical-context" id="eventTechnicalContext">' +
      '    <summary>Metadata t\u00e9cnica do evento</summary>' +
      '    <pre class="alert-evidence-json">' + Components.escape(_safeJSON(d)) + '</pre>' +
      '  </details>' +
      '</section>' +

      '<section class="event-flow-section event-impact-section" aria-labelledby="eventImpactHeading">' +
      '  <div class="event-section-heading"><span class="event-step-index">03</span><div><span class="page-eyebrow">Impacto</span><h2 id="eventImpactHeading">Leitura baseada nos fatos</h2></div></div>' +
      _impactHTML(a) +
      '</section>' +

      '<section class="event-flow-section event-decision-section" aria-labelledby="eventDecisionHeading">' +
      '  <div class="event-section-heading"><span class="event-step-index">04</span><div><span class="page-eyebrow">Decis\u00e3o</span><h2 id="eventDecisionHeading">Pr\u00f3xima a\u00e7\u00e3o operacional</h2></div></div>' +
      _decisionHTML(a) +
      '</section>' +

      '<section class="event-flow-section event-timeline-section" aria-labelledby="eventTimelineHeading">' +
      '  <div class="event-section-heading event-section-heading-compact"><span class="event-step-index">\u00b7</span><div><span class="page-eyebrow">Timeline</span><h2 id="eventTimelineHeading">Cadeia do evento</h2></div></div>' +
      _operationalTimelineHTML(a) +
      '</section>' +
      '</div>';
  }

  function _detailFact(label, value, mono) {
    return '<div><dt>' + Components.escape(label) + '</dt><dd' + (mono ? ' class="mono"' : '') + '>' + Components.escape(String(value || 'N\u00e3o informado')) + '</dd></div>';
  }

  function _changeLabel(a) {
    var d = a.details || {};
    var raw = String(d.change_type || d.event_type || a.title || '').toLowerCase();
    var labels = {
      added: 'Arquivo adicionado', file_added: 'Arquivo adicionado',
      modified: 'Arquivo modificado', file_modified: 'Arquivo modificado',
      removed: 'Arquivo removido', deleted: 'Arquivo removido', file_removed: 'Arquivo removido',
      hash_changed: 'Hash divergente', hash_mismatch: 'Hash divergente'
    };
    return labels[raw] || a.title || 'Mudan\u00e7a de integridade';
  }

  function _filePath(a) {
    var d = a.details || {};
    return _detailValue(d, ['file_path', 'path', 'target']) || a.target || 'N\u00e3o informado';
  }

  function _detailValue(details, keys) {
    for (var i = 0; i < keys.length; i += 1) {
      var value = details[keys[i]];
      if (value !== undefined && value !== null && String(value).trim()) return String(value);
    }
    return '';
  }

  function _formatDate(value) {
    if (!value) return 'N\u00e3o informado';
    var parsed = new Date(value);
    if (Number.isNaN(parsed.getTime())) return String(value).slice(0, 25).replace('T', ' ');
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit', second: '2-digit'
    }).format(parsed);
  }

  function _statusLabel(status) {
    var labels = { NEW: 'Aguardando revis\u00e3o', ACKNOWLEDGED: 'Revisado', RESOLVED: 'Resolvido', SUPPRESSED: 'Suprimido' };
    return labels[status] || status || 'N\u00e3o informado';
  }

  function _safeDeliveryState(value) {
    var allowed = ['loading', 'delivered', 'pending', 'disabled', 'temporary_failure', 'failed', 'unavailable'];
    var normalized = String(value || 'unavailable');
    return allowed.indexOf(normalized) >= 0 ? normalized : 'unavailable';
  }

  function _siemStatusHTML() {
    var context = state.siemContext || {};
    var delivery = _safeDeliveryState(context.delivery_state);
    return '<div class="siem-investigation-context state-' + delivery + '" id="siemInvestigationAction" aria-live="polite">' +
      '<span class="siem-state-dot" aria-hidden="true"></span>' +
      '<span class="siem-state-copy"><small>Entrega ao EDY SIEM</small><strong>' + Components.escape(context.label || 'Estado indispon\u00edvel') + '</strong>' +
      '<span>' + Components.escape(context.description || '') + '</span></span></div>';
  }

  function _hashComparisonHTML(d) {
    var previous = _detailValue(d, ['previous_hash', 'old_hash', 'old_digest', 'expected_hash']);
    var current = _detailValue(d, ['current_hash', 'new_hash', 'new_digest', 'actual_hash', 'hash', 'sha256']);
    var algorithm = _detailValue(d, ['hash_algorithm', 'algorithm']) || 'Algoritmo n\u00e3o informado';
    var previousCopy = previous ? '<button type="button" class="hash-copy-button" data-copy-value="' + Components.escape(previous) + '" onclick="AlertsPage.copyEvidence(this.dataset.copyValue)">Copiar</button>' : '';
    var currentCopy = current ? '<button type="button" class="hash-copy-button" data-copy-value="' + Components.escape(current) + '" onclick="AlertsPage.copyEvidence(this.dataset.copyValue)">Copiar</button>' : '';
    return '<div class="hash-comparison" aria-label="Compara\u00e7\u00e3o de hashes">' +
      '<div class="hash-comparison-head"><h3>Compara\u00e7\u00e3o criptogr\u00e1fica</h3><span>' + Components.escape(algorithm.toUpperCase()) + '</span></div>' +
      '<div class="hash-comparison-grid">' +
      '<div class="hash-value-block"><div><span>Hash anterior</span>' + previousCopy + '</div><code>' + Components.escape(previous || 'N\u00e3o dispon\u00edvel para este evento') + '</code></div>' +
      '<div class="hash-compare-arrow" aria-hidden="true">\u2192</div>' +
      '<div class="hash-value-block hash-value-current"><div><span>Hash atual</span>' + currentCopy + '</div><code>' + Components.escape(current || 'N\u00e3o dispon\u00edvel para este evento') + '</code></div>' +
      '</div></div>';
  }

  function _baselineContextHTML(a) {
    var d = a.details || {};
    var baselineId = _detailValue(d, ['baseline_id']);
    var baselineState = _detailValue(d, ['baseline_status', 'change_type']);
    var scanId = _detailValue(d, ['scan_id', 'correlation_id']);
    var presence = 'N\u00e3o informado';
    var stateLabel = baselineState || 'N\u00e3o classificado';
    if (baselineState === 'added') presence = 'N\u00e3o constava';
    else if (baselineState === 'modified' || baselineState === 'removed') presence = 'Sim';
    else if (baselineState === 'not_applicable') presence = 'N\u00e3o se aplica';
    var labels = { added: 'Adicionado ap\u00f3s a baseline', modified: 'Modificado desde a baseline', removed: 'Ausente no scan atual', created: 'Baseline criada', not_applicable: 'Sem baseline FIM' };
    stateLabel = labels[baselineState] || stateLabel;
    return '<div class="baseline-context"><div class="hash-comparison-head"><h3>Contexto da baseline</h3><span>' + Components.escape(baselineId || 'Sem baseline associada') + '</span></div>' +
      '<dl class="baseline-context-grid">' +
      _detailFact('Estava na baseline?', presence) +
      _detailFact('Primeiro registro', _formatDate(a.first_seen_at)) +
      _detailFact('Estado atual', stateLabel) +
      _detailFact('Scan relacionado', scanId || 'N\u00e3o informado', true) +
      '</dl></div>';
  }

  function _impactHTML(a) {
    var d = a.details || {};
    var facts = [];
    var baselineState = _detailValue(d, ['baseline_status', 'change_type']);
    var previous = _detailValue(d, ['previous_hash', 'old_hash', 'old_digest', 'expected_hash']);
    var current = _detailValue(d, ['current_hash', 'new_hash', 'new_digest', 'actual_hash', 'hash', 'sha256']);
    if (a.severity === 'CRITICAL') facts.push('A regra local classificou este evento com severidade cr\u00edtica.');
    if (baselineState === 'added') facts.push('O arquivo n\u00e3o constava na baseline associada.');
    if (baselineState === 'modified') facts.push('O arquivo consta na baseline e foi registrado como modificado.');
    if (baselineState === 'removed') facts.push('O arquivo constava na baseline e n\u00e3o foi encontrado no scan atual.');
    if (previous && current && previous !== current) facts.push('Os hashes anterior e atual s\u00e3o diferentes.');
    if ((previous && !current) || (!previous && current)) facts.push('A compara\u00e7\u00e3o criptogr\u00e1fica est\u00e1 parcial porque um dos hashes n\u00e3o foi registrado.');
    if (facts.length === 0) facts.push('A altera\u00e7\u00e3o ainda n\u00e3o possui classifica\u00e7\u00e3o adicional nos dados do evento.');
    return '<ul class="event-impact-list">' + facts.map(function (fact) {
      return '<li><span aria-hidden="true">\u2022</span><p>' + Components.escape(fact) + '</p></li>';
    }).join('') + '</ul><p class="event-impact-note">Orienta\u00e7\u00e3o limitada aos fatos registrados pelo Shield; nenhuma conclus\u00e3o de comprometimento foi inferida.</p>';
  }

  function _decisionHTML(a) {
    var context = state.siemContext || {};
    var canReview = a.status === 'NEW';
    var canResolve = a.status === 'NEW' || a.status === 'ACKNOWLEDGED';
    var canReopen = a.status === 'RESOLVED' || a.status === 'SUPPRESSED';
    var localPrimary = canReview
      ? '<button class="btn btn-primary" onclick="AlertsPage.individualActiveAction(\'ack\')">Marcar como revisado</button>'
      : '<span class="decision-state-label">Estado local: ' + Components.escape(_statusLabel(a.status)) + '</span>';
    var lifecycle = canResolve
      ? '<button class="btn btn-sm btn-ghost" onclick="AlertsPage.individualActiveAction(\'resolve\')">Resolver alerta</button>'
      : (canReopen ? '<button class="btn btn-sm btn-ghost" onclick="AlertsPage.individualActiveAction(\'reopen\')">Reabrir alerta</button>' : '');
    var fimAction = a.source === 'fim' || _detailValue(a.details || {}, ['baseline_id'])
      ? '<button class="btn btn-sm btn-ghost" onclick="AlertsPage.openFimTools()">Executar novo scan</button>' : '';
    var siemAction = '';
    if (context.can_investigate) {
      siemAction = '<button type="button" class="btn btn-primary siem-decision-button" onclick="AlertsPage.openSiemInvestigation()">Investigar no EDY SIEM <span aria-hidden="true">\u2197</span></button>';
    } else {
      siemAction = '<div class="siem-decision-unavailable"><strong>' + Components.escape(context.label || 'Investiga\u00e7\u00e3o indispon\u00edvel') + '</strong><span>' + Components.escape(context.description || 'A CTA ser\u00e1 liberada somente ap\u00f3s a entrega confirmada.') + '</span></div>';
    }
    return '<div class="decision-local-actions"><div><span class="decision-group-label">No Shield</span><div class="decision-button-row">' + localPrimary + lifecycle + fimAction + '<button class="btn btn-sm btn-ghost" onclick="AlertsPage.focusTechnicalContext()">Abrir contexto relacionado</button><button class="btn btn-sm btn-ghost" onclick="AlertsPage.exportJSON()">Exportar JSON</button></div></div>' +
      '<div class="decision-siem-lane"><span class="decision-group-label">Investiga\u00e7\u00e3o multi-sinal</span>' + siemAction + '</div></div>';
  }

  function _operationalTimelineHTML(a) {
    var context = state.siemContext || {};
    var items = [];
    function add(time, label, tone) {
      if (!time) return;
      items.push({ time: time, label: label, tone: tone });
    }
    add(context.event_timestamp || a.last_seen_at, 'Mudan\u00e7a registrada pelo Shield', 'local');
    if (a.first_seen_at && !_sameInstant(a.first_seen_at, context.event_timestamp || a.last_seen_at)) add(a.first_seen_at, 'Primeiro registro local deste alerta', 'local');
    add(context.queued_at, 'Evento enfileirado para o EDY SIEM', 'queued');
    if (context.last_attempt_at && !_sameInstant(context.last_attempt_at, context.delivered_at)) add(context.last_attempt_at, 'Tentativa de entrega ao EDY SIEM', 'queued');
    add(context.delivered_at, 'Recebimento confirmado pelo EDY SIEM', 'delivered');
    if (items.length === 0) return Components.emptyStateHTML('\u2205', 'Timeline indispon\u00edvel', 'Nenhum timestamp real foi registrado para este evento.');
    return '<ol class="event-operational-timeline">' + items.map(function (item) {
      return '<li class="timeline-tone-' + item.tone + '"><span class="event-timeline-dot" aria-hidden="true"></span><div><strong>' + Components.escape(item.label) + '</strong><time>' + Components.escape(_formatDate(item.time)) + '</time></div></li>';
    }).join('') + '</ol>';
  }

  function _sameInstant(first, second) {
    if (!first || !second) return false;
    var firstTime = new Date(first).getTime();
    var secondTime = new Date(second).getTime();
    if (!Number.isNaN(firstTime) && !Number.isNaN(secondTime)) return firstTime === secondTime;
    return String(first) === String(second);
  }

  function copyEvidence(value) {
    if (typeof value !== 'string' || !value) return;
    if (!navigator.clipboard || typeof navigator.clipboard.writeText !== 'function') {
      Toast.error('C\u00f3pia n\u00e3o dispon\u00edvel neste navegador.');
      return;
    }
    navigator.clipboard.writeText(value)
      .then(function () { Toast.success('Hash copiado.'); })
      .catch(function () { Toast.error('N\u00e3o foi poss\u00edvel copiar o hash.'); });
  }

  function individualActiveAction(action) {
    if (!state.activeAlert) return;
    individualAction(state.activeAlert.alert_id, action);
  }

  function openFimTools() {
    window.location.assign('/#fim');
  }

  function focusTechnicalContext() {
    var details = document.getElementById('eventTechnicalContext');
    if (!details) return;
    details.open = true;
    details.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  // --- Investigation Workspace: Tabs (M4.4.6) ---
  function switchTab(tab) {
    if (!state.activeAlert) return;
    document.querySelectorAll('.alert-side-panel-tab').forEach(function (b) {
      b.classList.toggle('active', b.getAttribute('data-tab') === tab);
    });
    var body = document.getElementById('panelBody');
    if (!body) return;
    var a = state.activeAlert;

    if (tab === 'summary') body.innerHTML = _tabSummary(a);
    else if (tab === 'timeline') body.innerHTML = _tabTimeline(a);
    else if (tab === 'evidence') body.innerHTML = _tabEvidence(a);
    else if (tab === 'comments') { body.innerHTML = Components.skeletonHTML('line', 3); _loadComments(body); }
    else if (tab === 'history') body.innerHTML = _tabHistory(a);
  }

  function _tabSummary(a) {
    var d = a.details || {};
    return '' +
      _field('Alvo / Asset', a.target || '-', true) +
      _field('Origem', a.source || '-') +
      _field('Regra', a.rule_id || '-', true) +
      _field('MITRE ATT&CK', d.mitre_attack || d.mitre || d.tactic || d.technique || '-') +
      _field('Usuário', d.user || d.username || d.account || '-', true) +
      _field('Processo', d.process || d.process_name || '-', true) +
      _field('Descrição', a.description || '-');
  }

  function _tabTimeline(a) {
    var items = [];
    if (a.first_seen_at) items.push({ t: a.first_seen_at, label: 'Primeira ocorrência', cls: 'info' });
    if (a.last_seen_at) items.push({ t: a.last_seen_at, label: 'Última ocorrência', cls: 'low' });
    if (a.acknowledged_at) items.push({ t: a.acknowledged_at, label: 'Reconhecido por ' + (a.acknowledged_by || 'sistema'), cls: 'medium' });
    if (a.resolved_at) items.push({ t: a.resolved_at, label: 'Resolvido por ' + (a.resolved_by || 'sistema'), cls: 'high' });
    if (a.resolution_note) items.push({ t: a.resolved_at || '', label: 'Nota: ' + a.resolution_note, cls: 'info' });
    if (items.length === 0) return Components.emptyStateHTML('\u2205', 'Sem eventos', 'Nenhum evento registrado para este alerta.');
    return '<div class="timeline">' + items.map(function (it) {
      return '<div class="timeline-item">' +
        '<div class="timeline-dot ' + it.cls + '">&#9679;</div>' +
        '<div class="timeline-content">' +
        '<div class="timeline-title">' + Components.escape(it.label) + '</div>' +
        '<div class="timeline-meta"><span>' + Components.escape((it.t || '').slice(0, 19).replace('T', ' ')) + '</span></div>' +
        '</div></div>';
    }).join('') + '</div>';
  }

  function _tabEvidence(a) {
    var d = a.details || {};
    var groups = [
      ['Hashes', _ev(d, ['hashes', 'hash', 'sha256', 'sha1', 'md5'], 'medium')],
      ['Caminhos', _ev(d, ['paths', 'path', 'files', 'file_path'], 'info')],
      ['IPs', _ev(d, ['ips', 'ip', 'src_ip', 'dst_ip', 'remote_ip'], 'high')],
      ['Dom\u00ednios', _ev(d, ['domains', 'domain', 'hostname'], 'low')],
      ['URLs', _ev(d, ['urls', 'url'], 'info')],
      ['IOCs', _ev(d, ['iocs', 'indicators'], 'critical')]
    ];
    var html = groups.filter(function (g) { return g[1]; }).map(function (g) {
      return '<div class="alert-side-panel-section">' +
        '<div class="alert-side-panel-section-title">' + g[0] + '</div>' + g[1] + '</div>';
    }).join('');

    if (!html) {
      html = Components.emptyStateHTML('\u26D3', 'Sem evid\u00eancias estruturadas',
        'Nenhum IOC estruturado encontrado. Confira o payload bruto abaixo.');
    }
    html += '<div class="alert-side-panel-section">' +
      '<div class="alert-side-panel-section-title">Payload Bruto</div>' +
      '<pre class="alert-evidence-json">' + Components.escape(_safeJSON(d)) + '</pre></div>';
    return html;
  }

  function _tabComments(body) {
    EDY.api('/api/alerts/' + state.activeAlert.alert_id + '/comments')
      .then(function (data) {
        var list = data.comments || [];
        var html = '<div class="alert-comments">';
        if (list.length === 0) {
          html += Components.emptyStateHTML('\uD83D\uDCDD', 'Sem comentários', 'Adicione a primeira nota de investigação.');
        } else {
          html += list.map(function (c) {
            return '<div class="alert-comment">' +
              '<div class="alert-comment-head"><strong>' + Components.escape(c.author || 'analyst') + '</strong>' +
              '<span>' + Components.escape((c.created_at || '').slice(0, 19).replace('T', ' ')) + '</span></div>' +
              '<div class="alert-comment-body">' + Components.escape(c.body || '') + '</div></div>';
          }).join('');
        }
        html += '</div>' +
          '<div class="alert-side-panel-comment-input">' +
          '<input type="text" id="panelNoteInput" placeholder="Adicionar comentário..." onkeydown="if(event.key===\'Enter\')AlertsPage.addComment()">' +
          '<button class="btn btn-sm btn-primary" onclick="AlertsPage.addComment()">Enviar</button></div>';
        body.innerHTML = html;
      })
      .catch(function () {
        body.innerHTML = Components.errorStateHTML('Erro', 'Falha ao carregar comentários.');
      });
  }

  function _tabHistory(a) {
    var rows = [];
    rows.push(['Criado', a.created_at || a.first_seen_at || '-']);
    rows.push(['Primeira ocorrência', a.first_seen_at || '-']);
    rows.push(['Última ocorrência', a.last_seen_at || '-']);
    rows.push(['Reconhecido', (a.acknowledged_at || '-') + (a.acknowledged_by ? ' por ' + a.acknowledged_by : '')]);
    rows.push(['Resolvido', (a.resolved_at || '-') + (a.resolved_by ? ' por ' + a.resolved_by : '')]);
    rows.push(['Count (dedup)', String(a.count || 1)]);
    return '<div class="alert-history">' + rows.map(function (r) {
      return '<div class="alert-history-row"><span>' + r[0] + '</span><strong>' + Components.escape(r[1]) + '</strong></div>';
    }).join('') + '</div>';
  }

  function addComment() {
    if (!state.activeAlert) return;
    var input = document.getElementById('panelNoteInput');
    var note = input ? input.value.trim() : '';
    if (!note) return;
    EDY.apiPost('/api/alerts/' + state.activeAlert.alert_id + '/comment', { author: 'analyst', body: note })
      .then(function () {
        Toast.success('Comentário adicionado.');
        switchTab('comments');
      })
      .catch(function (err) {
        Toast.error('Erro ao adicionar comentário: ' + err.message);
      });
  }

  function exportJSON() {
    if (!state.activeAlert) return;
    var blob = new Blob([JSON.stringify(state.activeAlert, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url;
    a.download = 'alert-' + state.activeAlert.alert_id + '.json';
    a.click();
    URL.revokeObjectURL(url);
  }

  // Helpers
  function _field(label, value, mono) {
    return '<div class="alert-side-panel-field">' +
      '<span class="alert-side-panel-field-label">' + label + '</span>' +
      '<span class="alert-side-panel-field-value' + (mono ? ' mono' : '') + '">' + Components.escape(String(value)) + '</span></div>';
  }

  function _ev(d, keys, cls) {
    var vals = [];
    keys.forEach(function (k) {
      var v = d[k];
      if (v === undefined || v === null) return;
      if (Array.isArray(v)) vals = vals.concat(v.map(String));
      else vals.push(String(v));
    });
    var uniq = [];
    vals.forEach(function (v) { if (uniq.indexOf(v) === -1) uniq.push(v); });
    if (uniq.length === 0) return '';
    return '<div class="alert-evidence-list">' + uniq.map(function (v) {
      return '<span class="alert-evidence-item alert-evidence-' + (cls || 'info') + '">' +
        Components.escape(v) + '</span>';
    }).join('') + '</div>';
  }

  function _safeJSON(d) {
    try { return JSON.stringify(d, null, 2); } catch (e) { return '{}'; }
  }

  function closePanel() {
    var panel = document.getElementById('alertSidePanel');
    var backdrop = document.getElementById('sidePanelBackdrop');
    if (panel) panel.classList.remove('open');
    if (backdrop) backdrop.classList.remove('open');
    state.activeAlert = null;
    state.siemContext = null;
    state.hostname = null;
  }

  function individualAction(id, action) {
    var noteInput = document.getElementById('panelNoteInput');
    var note = noteInput ? noteInput.value.trim() : '';

    EDY.apiPost('/api/alerts/' + id + '/' + action, {
      by: 'analyst',
      note: note || 'A\u00e7\u00e3o via Painel Lateral'
    })
    .then(function (updated) {
      Toast.success('Alerta ' + action.toUpperCase() + ' com sucesso.');
      closePanel();
      refresh();
    })
    .catch(function (err) {
      Toast.error('Erro ao executar a\u00e7\u00e3o: ' + err.message);
    });
  }

  return {
    refresh: refresh,
    onFilterChange: onFilterChange,
    onSearchInput: onSearchInput,
    sort: sort,
    goToPage: goToPage,
    toggleSelect: toggleSelect,
    toggleSelectAll: toggleSelectAll,
    clearSelection: clearSelection,
    batchAction: batchAction,
    onRowClick: onRowClick,
    closePanel: closePanel,
    individualAction: individualAction,
    switchTab: switchTab,
    addComment: addComment,
    exportJSON: exportJSON,
    openSiemInvestigation: openSiemInvestigation,
    copyEvidence: copyEvidence,
    individualActiveAction: individualActiveAction,
    openFimTools: openFimTools,
    focusTechnicalContext: focusTechnicalContext
  };
})();
