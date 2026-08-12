/**
 * EDY Shield — Endpoint Integrity Center (Product Redesign V1 / Sprint A1).
 *
 * The Home composes real data already exposed by the Shield: host health,
 * FIM baselines, scan history, local alerts and confirmed SIEM delivery.
 */

Router.register('dashboard', {
  title: 'Integridade do Endpoint',
  render: function () {
    return (
      '<div class="page-header integrity-page-header">' +
      '  <div class="page-header-left">' +
      '    <span class="page-eyebrow">Endpoint Integrity Center</span>' +
      '    <h1>Integridade do endpoint</h1>' +
      '    <p>Baseline, mudanças relevantes e próxima ação em um único contexto.</p>' +
      '  </div>' +
      '  <div class="integrity-header-actions">' +
      '    <div class="refresh-indicator" aria-live="polite">' +
      '      <span class="refresh-spinner" id="refreshSpinner"></span>' +
      '      <span id="refreshText">Dados atuais</span>' +
      '    </div>' +
      '    <button class="btn btn-primary btn-sm" onclick="Dashboard.refresh()">Atualizar</button>' +
      '  </div>' +
      '</div>' +

      '<section class="integrity-hero card" aria-labelledby="integrityStatusTitle">' +
      '  <div class="integrity-hero-status" id="integrityStatusBody">' +
      Components.skeletonHTML('line', 5) +
      '  </div>' +
      '  <div class="integrity-endpoint-panel" id="endpointFactsBody">' +
      Components.skeletonHTML('line', 5) +
      '  </div>' +
      '</section>' +

      '<section class="integrity-signal-strip" id="integritySignals" aria-label="Resumo da postura de integridade">' +
      Components.skeletonHTML('card', 3) +
      '</section>' +

      '<div class="integrity-workspace">' +
      '  <section class="card integrity-review-card" aria-labelledby="reviewQueueTitle">' +
      '    <div class="card-header integrity-card-header">' +
      '      <div><span class="page-eyebrow">Prioridade operacional</span><h2 id="reviewQueueTitle">Mudanças que exigem revisão</h2></div>' +
      '      <button class="btn btn-sm btn-ghost" onclick="Router.navigate(\'alerts\')">Ver central de alertas</button>' +
      '    </div>' +
      '    <div class="integrity-review-list" id="reviewQueueBody">' +
      Components.skeletonHTML('line', 5) +
      '    </div>' +
      '  </section>' +

      '  <aside class="integrity-action-rail" aria-label="Próxima ação e áreas protegidas">' +
      '    <section class="card next-action-card" id="nextActionBody">' +
      Components.skeletonHTML('line', 5) +
      '    </section>' +
      '    <section class="card protected-areas-card">' +
      '      <div class="card-header"><h2>Áreas protegidas</h2></div>' +
      '      <div class="protected-areas-list" id="protectedAreasBody">' +
      Components.skeletonHTML('line', 3) +
      '      </div>' +
      '    </section>' +
      '  </aside>' +
      '</div>'
    );
  },

  onLoad: function () {
    Dashboard._refreshHandler = function () { Dashboard.refresh(); };
    document.addEventListener('edy-refresh', Dashboard._refreshHandler);
    Dashboard.loadData();
  },

  onUnload: function () {
    if (Dashboard._refreshHandler) {
      document.removeEventListener('edy-refresh', Dashboard._refreshHandler);
      Dashboard._refreshHandler = null;
    }
    if (Router.abortFetch) Router.abortFetch();
  }
});

var Dashboard = {
  state: { model: null },

  refresh: function () {
    Dashboard._startSpinner();
    Dashboard.loadData();
  },

  loadData: function () {
    Promise.all([
      EDY.api('/api/health'),
      EDY.api('/api/fim/baselines'),
      EDY.api('/api/history'),
      EDY.api('/api/alerts?limit=50')
    ])
    .then(function (results) {
      var health = results[0] || {};
      var baselines = (results[1] && results[1].baselines) || [];
      var history = (results[2] && results[2].entries) || [];
      var alerts = (results[3] && results[3].alerts) || [];
      var fimEntries = history.filter(function (entry) {
        return entry.plugin_name === 'file_integrity';
      }).slice(0, 6);

      var detailRequests = fimEntries.map(function (entry) {
        return EDY.api('/api/history/' + encodeURIComponent(entry.id))
          .then(function (detail) { return { metadata: entry, detail: detail }; })
          .catch(function () { return { metadata: entry, detail: null }; });
      });

      var prioritized = Dashboard._prioritizeChanges(alerts);
      var siemRequest = prioritized.length > 0
        ? EDY.api('/api/integrations/edy-siem/alerts/' + encodeURIComponent(prioritized[0].alert_id))
            .catch(function () { return { delivery_state: 'unavailable', can_investigate: false }; })
        : Promise.resolve({ delivery_state: 'unavailable', can_investigate: false });

      return Promise.all([Promise.all(detailRequests), siemRequest]).then(function (extra) {
        return Dashboard._buildModel(
          health,
          baselines,
          alerts,
          prioritized,
          extra[0],
          extra[1]
        );
      });
    })
    .then(function (model) {
      Dashboard.state.model = model;
      Dashboard._render(model);
    })
    .catch(function (err) {
      if (err.name === 'AbortError') return;
      Dashboard._renderError(err);
      Toast.error('Não foi possível carregar a postura de integridade.');
    })
    .finally(function () {
      Dashboard._stopSpinner();
    });
  },

  _buildModel: function (health, baselines, alerts, prioritized, scanRecords, siem) {
    var activeBaseline = baselines.length > 0 ? baselines[0] : null;
    var latestOperation = scanRecords.length > 0 ? scanRecords[0] : null;
    var latestScan = scanRecords.find(function (record) {
      var stats = record.detail && record.detail.stats;
      return stats && ['added', 'modified', 'removed'].some(function (key) {
        return Object.prototype.hasOwnProperty.call(stats, key);
      });
    }) || null;
    var scanStats = latestScan && latestScan.detail ? latestScan.detail.stats || {} : {};
    var hasDriftData = latestScan !== null;
    var driftCount = hasDriftData
      ? Number(scanStats.added || 0) + Number(scanStats.modified || 0) + Number(scanStats.removed || 0)
      : null;
    var roots = activeBaseline && activeBaseline.root ? [activeBaseline.root] : [];
    var unresolved = alerts.filter(function (alert) {
      return alert.status !== 'RESOLVED' && alert.status !== 'SUPPRESSED';
    });
    var criticalCount = unresolved.filter(function (alert) { return alert.severity === 'CRITICAL'; }).length;
    var highMediumCount = unresolved.filter(function (alert) {
      return alert.severity === 'HIGH' || alert.severity === 'MEDIUM';
    }).length;
    var status = 'stable';
    if (!activeBaseline) status = 'missing';
    else if (criticalCount > 0) status = 'critical';
    else if (highMediumCount > 0 || (driftCount !== null && driftCount > 0)) status = 'review';
    else if (!latestScan) status = 'scan';

    return {
      health: health,
      hostname: health.hostname || 'Host não informado',
      activeBaseline: activeBaseline,
      roots: roots,
      latestOperation: latestOperation,
      latestScan: latestScan,
      driftCount: driftCount,
      prioritized: prioritized.slice(0, 5),
      unresolvedCount: unresolved.length,
      criticalCount: criticalCount,
      baselineEntries: activeBaseline ? Number(activeBaseline.entries || 0) : 0,
      status: status,
      siem: siem || { delivery_state: 'unavailable', can_investigate: false }
    };
  },

  _prioritizeChanges: function (alerts) {
    var rank = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, LOW: 1, INFO: 0 };
    return alerts.filter(function (alert) {
      return ['CRITICAL', 'HIGH', 'MEDIUM'].indexOf(alert.severity) !== -1 &&
        alert.status !== 'RESOLVED' && alert.status !== 'SUPPRESSED';
    }).sort(function (a, b) {
      var severityDiff = (rank[b.severity] || 0) - (rank[a.severity] || 0);
      if (severityDiff !== 0) return severityDiff;
      return String(b.last_seen_at || '').localeCompare(String(a.last_seen_at || ''));
    });
  },

  _render: function (model) {
    Dashboard._renderIntegrityStatus(model);
    Dashboard._renderEndpointFacts(model);
    Dashboard._renderSignals(model);
    Dashboard._renderReviewQueue(model);
    Dashboard._renderNextAction(model);
    Dashboard._renderProtectedAreas(model);
  },

  _statusCopy: function (status) {
    var copies = {
      critical: {
        label: 'Alteração crítica detectada',
        description: 'Uma mudança crítica não resolvida exige validação imediata.',
        icon: '!', tone: 'critical'
      },
      review: {
        label: 'Mudanças para revisar',
        description: 'Há drift ou alertas relevantes aguardando decisão do operador.',
        icon: '↗', tone: 'review'
      },
      missing: {
        label: 'Baseline ausente',
        description: 'O Shield ainda não possui uma referência de integridade para este endpoint.',
        icon: '—', tone: 'missing'
      },
      scan: {
        label: 'Scan necessário',
        description: 'A baseline existe, mas ainda não há comparação FIM disponível.',
        icon: '○', tone: 'scan'
      },
      stable: {
        label: 'Integridade estável',
        description: 'Nenhuma mudança relevante aguarda revisão neste momento.',
        icon: '✓', tone: 'stable'
      }
    };
    return copies[status] || copies.scan;
  },

  _renderIntegrityStatus: function (model) {
    var body = document.getElementById('integrityStatusBody');
    if (!body) return;
    var copy = Dashboard._statusCopy(model.status);
    body.className = 'integrity-hero-status integrity-state-' + copy.tone;
    body.innerHTML = '' +
      '<div class="integrity-status-mark" aria-hidden="true">' + copy.icon + '</div>' +
      '<div class="integrity-status-copy">' +
      '  <span class="integrity-status-kicker">Estado operacional</span>' +
      '  <h2 id="integrityStatusTitle">' + Components.escape(copy.label) + '</h2>' +
      '  <p>' + Components.escape(copy.description) + '</p>' +
      '  <div class="integrity-status-meta">' +
      '    <span><strong>' + model.criticalCount + '</strong> críticas abertas</span>' +
      '    <span><strong>' + model.unresolvedCount + '</strong> mudanças pendentes</span>' +
      '  </div>' +
      '</div>';
  },

  _renderEndpointFacts: function (model) {
    var body = document.getElementById('endpointFactsBody');
    if (!body) return;
    var baseline = model.activeBaseline;
    var scanTime = model.latestScan ? model.latestScan.metadata.timestamp : null;
    body.innerHTML = '' +
      '<div class="endpoint-identity">' +
      '  <span class="endpoint-identity-icon" aria-hidden="true">▣</span>' +
      '  <div><span class="endpoint-label">Endpoint protegido</span><strong>' + Components.escape(model.hostname) + '</strong></div>' +
      '</div>' +
      '<dl class="endpoint-facts">' +
      Dashboard._factHTML('Baseline ativa', baseline ? baseline.id : 'Não configurada', baseline ? 'ok' : 'attention') +
      Dashboard._factHTML('Último scan FIM', scanTime ? Dashboard._formatDate(scanTime) : 'Ainda não executado', scanTime ? 'ok' : 'attention') +
      Dashboard._factHTML('Áreas protegidas', String(model.roots.length), model.roots.length ? 'ok' : 'attention') +
      Dashboard._factHTML('Estado do agente', model.health.status === 'online' ? 'Operacional' : 'Degradado', model.health.status === 'online' ? 'ok' : 'attention') +
      '</dl>';
  },

  _factHTML: function (label, value, state) {
    return '<div class="endpoint-fact"><dt>' + Components.escape(label) + '</dt><dd><span class="fact-state fact-state-' + state + '" aria-hidden="true"></span>' + Components.escape(value) + '</dd></div>';
  },

  _renderSignals: function (model) {
    var body = document.getElementById('integritySignals');
    if (!body) return;
    var drift = model.driftCount === null ? '—' : String(model.driftCount);
    body.innerHTML = '' +
      Dashboard._signalHTML('Arquivos na baseline', model.activeBaseline ? String(model.baselineEntries) : '—', 'Referência criptográfica ativa') +
      Dashboard._signalHTML('Mudanças no último scan', drift, model.driftCount === null ? 'Comparação ainda indisponível' : 'Adicionados, modificados ou removidos') +
      Dashboard._signalHTML('Revisões pendentes', String(model.unresolvedCount), 'Alertas locais ainda não encerrados');
  },

  _signalHTML: function (label, value, detail) {
    return '<article class="integrity-signal">' +
      '<span class="integrity-signal-label">' + Components.escape(label) + '</span>' +
      '<strong>' + Components.escape(value) + '</strong>' +
      '<span class="integrity-signal-detail">' + Components.escape(detail) + '</span>' +
      '</article>';
  },

  _renderReviewQueue: function (model) {
    var body = document.getElementById('reviewQueueBody');
    if (!body) return;
    if (model.prioritized.length === 0) {
      body.innerHTML = Components.emptyStateHTML(
        '✓',
        'Nenhuma mudança prioritária',
        'Não há alertas críticos, altos ou médios aguardando revisão.'
      );
      return;
    }
    body.innerHTML = model.prioritized.map(function (alert) {
      var details = alert.details || {};
      var evidence = [];
      if (details.baseline_id) evidence.push('baseline');
      if (details.old_hash || details.new_hash || details.hash || details.hexdigest) evidence.push('hash');
      var evidenceHTML = evidence.length
        ? evidence.map(function (item) { return '<span class="change-evidence-tag">' + Components.escape(item) + '</span>'; }).join('')
        : '<span class="change-evidence-tag muted">evidência local</span>';
      return '<article class="integrity-change-item severity-' + String(alert.severity || 'INFO').toLowerCase() + '">' +
        '<div class="change-severity-column">' + Components.severityBadgeHTML(alert.severity) + '</div>' +
        '<div class="change-main">' +
        '  <div class="change-title-row"><strong>' + Components.escape(alert.title || 'Mudança de integridade') + '</strong>' + Components.statusBadgeHTML(alert.status) + '</div>' +
        '  <div class="change-path" title="' + Components.escape(alert.target || '') + '">' + Components.escape(alert.target || 'Caminho não informado') + '</div>' +
        '  <div class="change-meta"><span>' + Components.escape(Dashboard._changeType(alert)) + '</span><span>' + Components.escape(model.hostname) + '</span><span>' + Components.escape(Dashboard._formatDate(alert.last_seen_at)) + '</span></div>' +
        '  <div class="change-evidence">' + evidenceHTML + '</div>' +
        '</div>' +
        '<button class="btn btn-sm btn-ghost change-open-button" data-alert-id="' + Components.escape(alert.alert_id || '') + '" onclick="Dashboard.openAlert(this.dataset.alertId)" aria-label="Abrir detalhe da mudança">Abrir detalhe</button>' +
        '</article>';
    }).join('');
  },

  _changeType: function (alert) {
    var details = alert.details || {};
    var value = String(details.change_type || details.event_type || '').toLowerCase();
    var labels = { added: 'Arquivo adicionado', modified: 'Arquivo modificado', removed: 'Arquivo removido', deleted: 'Arquivo removido' };
    if (labels[value]) return labels[value];
    return alert.source === 'fim' ? 'Mudança FIM' : (alert.source || 'Evento local');
  },

  _renderNextAction: function (model) {
    var body = document.getElementById('nextActionBody');
    if (!body) return;
    var action = Dashboard._nextAction(model);
    var siem = model.siem || {};
    var siemButton = '';
    if (siem.can_investigate && typeof siem.investigation_url === 'string') {
      siemButton = '<button class="btn btn-sm siem-action-button" onclick="Dashboard.openSiem()">Investigar no EDY SIEM <span aria-hidden="true">↗</span></button>';
    }
    var siemLabel = siem.label || 'Evento SIEM indisponível';
    body.innerHTML = '' +
      '<span class="page-eyebrow">Decisão orientada pelo estado</span>' +
      '<h2>Próxima ação</h2>' +
      '<div class="next-action-priority">' + Components.escape(action.title) + '</div>' +
      '<p>' + Components.escape(action.description) + '</p>' +
      '<div class="next-action-buttons">' +
      '  <button class="btn btn-primary" onclick="' + action.onclick + '">' + Components.escape(action.button) + '</button>' +
      siemButton +
      '</div>' +
      '<div class="siem-readiness"><span class="fact-state fact-state-' + (siem.can_investigate ? 'ok' : 'neutral') + '" aria-hidden="true"></span><span>EDY SIEM: ' + Components.escape(siemLabel) + '</span></div>';
  },

  _nextAction: function (model) {
    if (model.status === 'critical') return {
      title: 'Revisar mudança crítica',
      description: 'Valide o arquivo afetado, os hashes e a relação com a baseline antes de encerrar o alerta.',
      button: 'Abrir mudança crítica', onclick: 'Dashboard.openTopAlert()'
    };
    if (model.status === 'review') return {
      title: 'Revisar drift do endpoint',
      description: 'Há mudanças relevantes aguardando classificação e decisão operacional.',
      button: 'Revisar mudanças', onclick: model.prioritized.length > 0 ? 'Dashboard.openTopAlert()' : "Router.navigate('alerts')"
    };
    if (model.status === 'missing') return {
      title: 'Criar a primeira baseline',
      description: 'Defina uma referência criptográfica antes de avaliar drift neste endpoint.',
      button: 'Abrir ferramentas de proteção', onclick: 'Dashboard.openTools()'
    };
    if (model.status === 'scan') return {
      title: 'Executar um scan de integridade',
      description: 'Compare o estado atual do host com a baseline ativa para identificar mudanças.',
      button: 'Abrir ferramentas de proteção', onclick: 'Dashboard.openTools()'
    };
    return {
      title: 'Manter a postura verificada',
      description: 'A integridade está estável. Atualize os dados quando houver uma nova janela de verificação.',
      button: 'Atualizar estado', onclick: 'Dashboard.refresh()'
    };
  },

  _renderProtectedAreas: function (model) {
    var body = document.getElementById('protectedAreasBody');
    if (!body) return;
    if (model.roots.length === 0) {
      body.innerHTML = Components.emptyStateHTML('▣', 'Nenhuma área protegida', 'Crie uma baseline para registrar o primeiro diretório monitorado.');
      return;
    }
    body.innerHTML = model.roots.slice(0, 4).map(function (root) {
      return '<div class="protected-area-item"><span class="protected-area-mark" aria-hidden="true">✓</span><span title="' + Components.escape(root) + '">' + Components.escape(root) + '</span></div>';
    }).join('') + (model.roots.length > 4 ? '<div class="protected-area-more">+' + (model.roots.length - 4) + ' áreas adicionais</div>' : '');
  },

  _renderError: function (err) {
    var description = err && err.message ? err.message : 'Tente novamente em alguns instantes.';
    var status = document.getElementById('integrityStatusBody');
    var facts = document.getElementById('endpointFactsBody');
    var signals = document.getElementById('integritySignals');
    var queue = document.getElementById('reviewQueueBody');
    var action = document.getElementById('nextActionBody');
    var areas = document.getElementById('protectedAreasBody');
    if (status) status.innerHTML = Components.errorStateHTML('Postura indisponível', description);
    if (facts) facts.innerHTML = Components.errorStateHTML('Endpoint indisponível', 'Os dados do host não puderam ser consultados.');
    if (signals) signals.innerHTML = Dashboard._signalHTML('Dados indisponíveis', '—', 'A atualização falhou');
    if (queue) queue.innerHTML = Components.errorStateHTML('Mudanças indisponíveis', 'A fila não pôde ser carregada.');
    if (action) action.innerHTML = '<span class="page-eyebrow">Recuperação</span><h2>Próxima ação</h2><p>Restaure a conexão com a API e tente novamente.</p><button class="btn btn-primary" onclick="Dashboard.refresh()">Tentar novamente</button>';
    if (areas) areas.innerHTML = Components.errorStateHTML('Áreas indisponíveis', 'Não foi possível consultar as baselines.');
  },

  _formatDate: function (value) {
    if (!value) return 'Não informado';
    var date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value).slice(0, 19).replace('T', ' ');
    return new Intl.DateTimeFormat('pt-BR', {
      day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit'
    }).format(date);
  },

  openAlert: function (alertId) {
    if (!alertId) return;
    sessionStorage.setItem('edy-shield-open-alert', alertId);
    Router.navigate('alerts');
  },

  openTopAlert: function () {
    var model = Dashboard.state.model;
    var top = model && model.prioritized ? model.prioritized[0] : null;
    Dashboard.openAlert(top ? top.alert_id : '');
  },

  openTools: function () {
    window.location.assign('/');
  },

  openSiem: function () {
    var model = Dashboard.state.model;
    var url = model && model.siem ? model.siem.investigation_url : null;
    if (typeof url !== 'string' || !/^https?:\/\//i.test(url)) return;
    window.open(url, '_blank', 'noopener,noreferrer');
  },

  _startSpinner: function () {
    var spinner = document.getElementById('refreshSpinner');
    if (spinner) spinner.classList.add('active');
    var text = document.getElementById('refreshText');
    if (text) text.textContent = 'Atualizando...';
  },

  _stopSpinner: function () {
    var spinner = document.getElementById('refreshSpinner');
    if (spinner) spinner.classList.remove('active');
    var text = document.getElementById('refreshText');
    if (text) text.textContent = 'Dados atuais';
  }
};
