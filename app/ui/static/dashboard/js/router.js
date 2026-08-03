/**
 * EDY Shield Dashboard — SPA Router (M4.1)
 *
 * Roteamento client-side baseado em hash (#/dashboard, #/alerts, etc).
 * Suporta navegação programática e transição entre páginas.
 *
 * O router registra páginas em um mapa e renderiza a página ativa no
 * contâiner #pageContainer. Cada página é uma função que retorna HTML.
 */

var Router = (function () {
  'use strict';

  var routes = {};
  var currentRoute = null;
  var pageContainer = null;

  /**
   * Inicializa o router com o contâiner de páginas.
   * @param {HTMLElement} container - Elemento onde as páginas renderizam.
   */
  function init(container) {
    pageContainer = container;
    window.addEventListener('hashchange', _onHashChange);
    _onHashChange();
  }

  /**
   * Registra uma rota.
   * @param {string} path - Caminho da rota (ex: 'dashboard', 'alerts').
   * @param {object} config - { title, render: function() -> string }
   */
  function register(path, config) {
    routes[path] = config;
  }

  /**
   * Navega para uma rota programaticamente.
   * @param {string} path - Caminho da rota.
   */
  function navigate(path) {
    window.location.hash = '#/' + path;
  }

  function _onHashChange() {
    var hash = window.location.hash.slice(2) || 'dashboard';
    var route = routes[hash];

    // Fallback para dashboard se rota não existe
    if (!route) {
      hash = 'dashboard';
      route = routes[hash];
    }

    currentRoute = hash;

    // Atualizar título
    var topbarTitle = document.getElementById('topbarTitle');
    if (topbarTitle && route) {
      topbarTitle.textContent = route.title || 'Dashboard';
    }

    // Atualizar nav items ativos
    var navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(function (item) {
      var itemRoute = item.getAttribute('data-route');
      if (itemRoute === hash) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Renderizar página
    if (pageContainer && route && typeof route.render === 'function') {
      pageContainer.innerHTML = '<div class="page-view">' + route.render() + '</div>';
    }
  }

  /**
   * Retorna a rota atual.
   * @returns {string|null} Rota atual.
   */
  function getCurrentRoute() {
    return currentRoute;
  }

  return {
    init: init,
    register: register,
    navigate: navigate,
    getCurrentRoute: getCurrentRoute
  };
})();