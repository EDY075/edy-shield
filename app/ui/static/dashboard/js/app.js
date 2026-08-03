/**
 * EDY Shield Dashboard — Bootstrap (M4.2.2 - Blue Team Overview)
 *
 * Inicializa o router, sidebar, tema dark/light, indicador online,
 * pesquisa global e intera\u00e7\u00f5es globais do dashboard Blue Team.
 * Gest\u00e3o de timers: single-interval auto-refresh + single-interval health check.
 * Todos os listeners s\u00e3o adicionados UMA vez, guardados para n\u00e3o duplicar.
 */

(function () {
  'use strict';

  var AUTO_REFRESH_INTERVAL = 30000; // 30s
  var HEALTH_CHECK_INTERVAL = 60000; // 60s

  var refreshTimer = null;
  var healthTimer = null;
  var refreshListener = null;

  document.addEventListener('DOMContentLoaded', function () {

    // --- Tema: carregar prefer\u00eancia salva ---
    var savedTheme = _getStoredTheme();
    document.documentElement.setAttribute('data-theme', savedTheme);
    _updateThemeToggleIcon(savedTheme);

    // --- Inicializar Router ---
    var pageContainer = document.getElementById('pageContainer');
    Router.init(pageContainer);

    // --- Sidebar: navega\u00e7\u00e3o (listener \u00fanico) ---
    document.querySelectorAll('.nav-item').forEach(function (item) {
      item.addEventListener('click', function () {
        var route = item.getAttribute('data-route');
        if (route) {
          Router.navigate(route);
          var sidebar = document.getElementById('sidebar');
          sidebar.classList.remove('mobile-open');
        }
      });
    });

    // --- Sidebar: colapsar/expandir ---
    var collapseBtn = document.getElementById('collapseBtn');
    if (collapseBtn) {
      collapseBtn.addEventListener('click', function () {
        var sidebar = document.getElementById('sidebar');
        if (window.innerWidth <= 1024) {
          sidebar.classList.toggle('mobile-open');
        } else {
          sidebar.classList.toggle('collapsed');
        }
      });
    }

    // --- Topbar: menu mobile ---
    var mobileMenuBtn = document.getElementById('mobileMenuBtn');
    if (mobileMenuBtn) {
      mobileMenuBtn.style.display = window.innerWidth <= 1024 ? 'flex' : 'none';
      mobileMenuBtn.addEventListener('click', function () {
        var sidebar = document.getElementById('sidebar');
        sidebar.classList.toggle('mobile-open');
      });
    }

    // --- Toggle de Tema ---
    var themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
      themeToggle.addEventListener('click', function () {
        var current = document.documentElement.getAttribute('data-theme') || 'dark';
        var next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        _storeTheme(next);
        _updateThemeToggleIcon(next);
        Toast.info('Tema alterado para ' + (next === 'dark' ? 'Escuro' : 'Claro'));
      });
    }

    // --- Topbar: busca global ---
    var searchInput = document.getElementById('globalSearch');
    if (searchInput) {
      searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && searchInput.value.trim()) {
          Router.navigate('alerts');
          Toast.info('Buscando: ' + searchInput.value.trim());
        }
      });
    }

    // --- Indicador Online/Offline ---
    _checkOnlineStatus();

    // --- Sidebar: Status do Sistema (M4.4.2) ---
    _loadSidebarStatus();

    // --- Topbar: Refresh (M4.4.3) ---
    var refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', function () {
        var icon = refreshBtn.querySelector('.topbar-refresh-icon');
        if (icon) icon.classList.add('rotating');
        document.dispatchEvent(new CustomEvent('edy-refresh'));
        setTimeout(function () {
          if (icon) icon.classList.remove('rotating');
        }, 800);
      });
    }

    // --- Topbar: Badge de Notificações (M4.4.3) ---
    _loadNotifBadge();

    // --- Updated auto-refresh: single listener + single timer ---
    _setupAutoRefresh();

    // --- Responsividade ---
    window.addEventListener('resize', function () {
      if (mobileMenuBtn) {
        mobileMenuBtn.style.display = window.innerWidth <= 1024 ? 'flex' : 'none';
      }
    });

    // --- Toast de boas-vindas ---
    setTimeout(function () {
      Toast.info('Dados reais carregados via API. Auto-refresh a cada 30s.', 'EDY Shield M4.2');
    }, 800);
  });

  // --- Tema helpers ---
  function _getStoredTheme() {
    try {
      return localStorage.getItem('edy-shield-theme') || 'dark';
    } catch (e) {
      return 'dark';
    }
  }

  function _storeTheme(theme) {
    try {
      localStorage.setItem('edy-shield-theme', theme);
    } catch (e) {
      // ignore
    }
  }

  function _updateThemeToggleIcon(theme) {
    var icon = document.getElementById('themeToggleIcon');
    if (icon) {
      icon.textContent = theme === 'dark' ? '\u2600' : '\uD83C\uDF19';
    }
  }

  // --- Indicador Online ---
  function _checkOnlineStatus() {
    fetch('/api/health')
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        var online = data.status === 'online';
        var indicator = document.getElementById('onlineIndicator');
        var text = document.getElementById('onlineIndicatorText');
        if (indicator) {
          if (online) {
            indicator.classList.add('online');
            indicator.title = 'Servidor online';
          } else {
            indicator.classList.remove('online');
            indicator.title = 'Servidor degradado';
          }
        }
        if (text) {
          text.textContent = online ? 'Online' : 'Degradado';
        }
      })
      .catch(function () {
        var indicator = document.getElementById('onlineIndicator');
        var text = document.getElementById('onlineIndicatorText');
        if (indicator) {
          indicator.classList.remove('online');
          indicator.title = 'Servidor offline';
        }
        if (text) text.textContent = 'Offline';
      });
  }

  // --- Sidebar Status do Sistema (M4.4.2) ---
  function _loadSidebarStatus() {
    Promise.all([
      fetch('/api/health').then(function (r) { return r.ok ? r.json() : null; }),
      fetch('/api/plugins').then(function (r) { return r.ok ? r.json() : null; })
    ]).then(function (results) {
      var health = results[0];
      var plugins = results[1];
      if (!health) return;

      var dotApi = document.getElementById('sbApiDot');
      var textApi = document.getElementById('sbApiText');
      if (dotApi && textApi) {
        dotApi.className = 'sidebar-status-dot ' + (health.status === 'online' ? 'ok' : 'degraded');
        textApi.textContent = health.status === 'online' ? 'Online' : 'Degradado';
      }

      var dotDb = document.getElementById('sbDbDot');
      var textDb = document.getElementById('sbDbText');
      if (dotDb && textDb) {
        var dbOk = health.sqlite && health.sqlite.status === 'ok';
        dotDb.className = 'sidebar-status-dot ' + (dbOk ? 'ok' : 'error');
        textDb.textContent = dbOk ? 'Saudável' : 'Erro';
      }

      var dotAna = document.getElementById('sbAnaDot');
      var textAna = document.getElementById('sbAnaText');
      if (dotAna && textAna) {
        var count = (health.analyzers && health.analyzers.count) || 0;
        dotAna.className = 'sidebar-status-dot ' + (count > 0 ? 'ok' : 'degraded');
        textAna.textContent = count + '/' + count + ' Online';
      }

      var textVer = document.getElementById('sbVerText');
      if (textVer && plugins && plugins.version) {
        textVer.textContent = 'v' + plugins.version;
      }
    }).catch(function () {
      var dotApi = document.getElementById('sbApiDot');
      var textApi = document.getElementById('sbApiText');
      if (dotApi && textApi) {
        dotApi.className = 'sidebar-status-dot error';
        textApi.textContent = 'Offline';
      }
    });
  }

  // --- Topbar: Badge de Notificações (M4.4.3) ---
  function _loadNotifBadge() {
    fetch('/api/alerts/stats')
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        var badge = document.getElementById('notifBadge');
        if (!badge || !data) return;
        var count = (data.new || 0) + (data.ack || 0);
        if (count > 0) {
          badge.textContent = count > 99 ? '99+' : String(count);
          badge.style.display = 'flex';
        } else {
          badge.style.display = 'none';
        }
      })
      .catch(function () { /* silencioso */ });
  }

  // --- Auto-refresh: listener \u00fanico + timer \u00fanico ---
  function _setupAutoRefresh() {
    // Remover listener anterior se existir
    if (refreshListener) {
      document.removeEventListener('edy-refresh', refreshListener);
    }

    // Criar novo listener
    refreshListener = function () {
      var hash = window.location.hash.slice(2) || 'dashboard';
      var route = Router.getCurrentRoute ? Router.getCurrentRoute() : null;
      if (!route || hash !== route) return;
      var handlers = { dashboard: true, health: true, alerts: true };
      if (handlers[hash]) {
        var pageObj = window[hash.charAt(0).toUpperCase() + hash.slice(1) + 'Page'];
        if (pageObj && typeof pageObj.refresh === 'function') {
          pageObj.refresh();
        }
      }
    };
    document.addEventListener('edy-refresh', refreshListener);

    // Limpar timer anterior
    if (refreshTimer) clearInterval(refreshTimer);

    // Novo timer \u00fanico
    refreshTimer = setInterval(function () {
      document.dispatchEvent(new CustomEvent('edy-refresh'));
    }, AUTO_REFRESH_INTERVAL);

    // Health check timer \u00fanico
    if (healthTimer) clearInterval(healthTimer);
    healthTimer = setInterval(_checkOnlineStatus, HEALTH_CHECK_INTERVAL);
  }

  // --- Na mudanca de p\u00e1gina, cancelar fetchs pendentes ---
  window.addEventListener('beforeunload', function () {
    if (refreshTimer) clearInterval(refreshTimer);
    if (healthTimer) clearInterval(healthTimer);
    if (refreshListener) document.removeEventListener('edy-refresh', refreshListener);
  });

  // --- API Helper global ---
  window.EDY = {
    api: function (path) {
      return fetch(path).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      });
    },
    apiPost: function (path, body) {
      return fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body || {})
      }).then(function (r) {
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return r.json();
      });
    },
    checkOnline: _checkOnlineStatus,
    getTheme: function () {
      return document.documentElement.getAttribute('data-theme') || 'dark';
    },
    abortFetch: function () {
      if (Router.abortFetch) Router.abortFetch();
    }
  };

})();
