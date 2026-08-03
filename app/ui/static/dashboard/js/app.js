/**
 * EDY Shield Dashboard — Bootstrap (M4.1)
 *
 * Inicializa o router, sidebar e interações globais do dashboard.
 */

(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
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
          // Fechar sidebar mobile se aberta
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

    // --- Topbar: busca global ---
    var searchInput = document.getElementById('globalSearch');
    if (searchInput) {
      searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' && searchInput.value.trim()) {
          Toast.info('Buscando: ' + searchInput.value + ' (demo)');
        }
      });
    }

    // --- WebSocket status placeholder ---
    // Estrutura preparada — implementação futura em M4.2+
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

    // --- Toast de boas-vindas ---
    setTimeout(function () {
      Toast.info(
        'Estrutura M4.1 carregada. Dados reais chegarão em M4.2+.',
        'EDY Shield Dashboard'
      );
    }, 500);

    // --- Responsividade: reavaliar ao redimensionar ---
    window.addEventListener('resize', function () {
      if (mobileMenuBtn) {
        mobileMenuBtn.style.display = window.innerWidth <= 1024 ? 'flex' : 'none';
      }
    });
  });
})();