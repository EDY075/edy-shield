/**
 * EDY Shield Dashboard — Bootstrap (M4.2 - Blue Team Overview)
 *
 * Inicializa o router, sidebar, tema dark/light, indicador online,
 * pesquisa global e interações globais do dashboard Blue Team.
 */

(function () {
  'use strict';

  var AUTO_REFRESH_INTERVAL = 30000; // 30s
  var refreshTimer = null;

  document.addEventListener('DOMContentLoaded', function () {

    // --- Tema: carregar preferência salva ---
    var savedTheme = localStorage.getItem('edy-shield-theme') || 'dark';
    document.documentElement.setAttribute('data-theme', savedTheme);
    _updateThemeToggleIcon(savedTheme);

    // --- Inicializar Router ---
    var pageContainer = document.getElementById('pageContainer');
    Router.init(pageContainer);

    // --- Sidebar: navegação ---
    var navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(function (item) {
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
        localStorage.setItem('edy-shield-theme', next);
        _updateThemeToggleIcon(next);
        Toast.info('Tema alterado para ' + (next === 'dark' ? 'Escuro' : 'Claro'));
      });
    }

    // --- Topbar: busca global ---
    var searchInput = document.getElementById('globalSearch');
    if (searchInput) {
      searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && searchInput.value.trim()) {
          var query = searchInput.value.trim();
          Router.navigate('alerts');
          Toast.info('Buscando: ' + query);
        }
      });
    }

    // --- Indicador Online/Offline ---
    _checkOnlineStatus();

    // --- Atualização automática dos dados ---
    _startAutoRefresh();

    // --- Responsividade: reavaliar ao redimensionar ---
    window.addEventListener('resize', function () {
      if (mobileMenuBtn) {
        mobileMenuBtn.style.display = window.innerWidth <= 1024 ? 'flex' : 'none';
      }
    });

    // --- Toast de boas-vindas ---
    setTimeout(function () {
      Toast.info('Dados reais carregados via API. Auto-refresh a cada 30s.', 'EDY Shield M4.2');
    }, 800);

    // --- WebSocket status placeholder ---
    var wsStatus = document.getElementById('wsStatus');
    var wsStatusText = document.getElementById('wsStatusText');
    function _updateWSStatus(connected) {
      if (connected) {
        wsStatus.classList.add('connected');
        wsStatusText.textContent = 'WS Ativo';
        wsStatus.title = 'WebSocket conectado';
      } else {
        wsStatus.classList.remove('connected');
        wsStatusText.textContent = 'Offline';
        wsStatus.title = 'WebSocket desconectado';
      }
    }
  });

  // --- Helpers globais ---

  function _updateThemeToggleIcon(theme) {
    var icon = document.getElementById('themeToggleIcon');
    if (icon) {
      icon.textContent = theme === 'dark' ? '\u2600' : '\uD83C\uDF19';
    }
  }

  function _checkOnlineStatus() {
    fetch('/api/health')
      .then(function (resp) { return resp.json(); })
      .then(function (data) {
        var online = data.status === 'online';
        var indicator = document.getElementById('onlineIndicator');
        if (indicator) {
          if (online) {
            indicator.classList.add('online');
            indicator.title = 'Servidor online';
          } else {
            indicator.classList.remove('online');
            indicator.title = 'Servidor degradado';
          }
        }
      })
      .catch(function () {
        var indicator = document.getElementById('onlineIndicator');
        if (indicator) {
          indicator.classList.remove('online');
          indicator.title = 'Servidor offline';
        }
      });
  }

  function _startAutoRefresh() {
    if (refreshTimer) clearInterval(refreshTimer);
    refreshTimer = setInterval(function () {
      // Emitir evento customizado para as páginas se atualizarem
      var event = new CustomEvent('edy-refresh');
      document.dispatchEvent(event);
    }, AUTO_REFRESH_INTERVAL);
  }

  // --- API Helper global exposto ---
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
    }
  };

  // Verificar status online a cada 60s
  setInterval(_checkOnlineStatus, 60000);

})();