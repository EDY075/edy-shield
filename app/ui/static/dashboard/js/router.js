/**
 * EDY Shield Dashboard — SPA Router (M4.2.2)
 *
 * Roteamento client-side baseado em hash (#/dashboard, #/alerts, etc).
 * Suporta ciclo de vida completo: onLoad, onUnload, loading global,
 * tratamento de erro de rota, cancelamento de fetch concorrentes.
 *
 * Cada página registrada pode ter:
 *   - render()      -> string HTML
 *   - onLoad()     -> chamado UMA vez após render
 *   - onUnload()   -> chamado antes de trocar de página (limpeza)
 */

var Router = (function () {
  'use strict';

  var routes = {};
  var currentRoute = null;
  var pageContainer = null;
  var loading = false;
  var fetchController = null;

  function init(container) {
    pageContainer = container;
    window.addEventListener('hashchange', _onHashChange);
    _onHashChange();
  }

  function register(path, config) {
    routes[path] = config;
  }

  function navigate(path) {
    window.location.hash = '#/' + path;
  }

  function _abortPendingFetch() {
    if (fetchController) {
      fetchController.abort();
      fetchController = null;
    }
  }

  function _onHashChange() {
    var hash = window.location.hash.slice(2) || 'dashboard';
    var route = routes[hash];

    // Fallback para dashboard se rota não existe
    if (!route) {
      hash = 'dashboard';
      route = routes[hash];
    }

    // Não recarregar se já está na mesma rota
    if (currentRoute === hash) return;

    // --- onUnload: limpar página anterior ---
    var prevRoute = currentRoute ? routes[currentRoute] : null;
    if (prevRoute && typeof prevRoute.onUnload === 'function') {
      try {
        prevRoute.onUnload();
      } catch (e) {
        console.warn('Router.onUnload error:', e);
      }
    }

    // Cancelar qualquer fetch pendente da página anterior
    _abortPendingFetch();

    // Atualizar estado
    currentRoute = hash;

    // Atualizar título
    var topbarTitle = document.getElementById('topbarTitle');
    if (topbarTitle) {
      topbarTitle.textContent = route ? route.title : 'Dashboard';
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

    // Loading global durante troca
    if (pageContainer) {
      pageContainer.innerHTML =
        '<div class="page-view">' +
        '<div class="loading-container"><div><div class="spinner"></div>' +
        '<div class="loading-text">Carregando...</div></div></div></div>';
    }

    // Renderizar página com pequeno delay para mostrar o loading
    setTimeout(function () {
      if (!pageContainer || !route || typeof route.render !== 'function') {
        if (pageContainer) {
          pageContainer.innerHTML =
            '<div class="page-view">' +
            Components.errorStateHTML('Rota n\u00e3o encontrada',
              'A p\u00e1gina solicitada n\u00e3o existe.') +
            '</div>';
        }
        return;
      }

      try {
        pageContainer.innerHTML = '<div class="page-view">' + route.render() + '</div>';
      } catch (e) {
        pageContainer.innerHTML =
          '<div class="page-view">' +
          Components.errorStateHTML('Erro ao renderizar',
            'Ocorreu um erro ao carregar esta p\u00e1gina: ' + e.message) +
          '</div>';
        return;
      }

      // Disparar onLoad UMA vez, com tratamento de erro
      if (typeof route.onLoad === 'function') {
        try {
          route.onLoad();
        } catch (e) {
          console.error('Router.onLoad error:', e);
          Toast.error('Erro ao carregar dados da p\u00e1gina');
        }
      }
    }, 50); // 50ms para mostrar o loading
  }

  function getCurrentRoute() {
    return currentRoute;
  }

  /**
   * Criar um AbortController para fetch cancelável nas páginas.
   */
  function createSignal() {
    _abortPendingFetch();
    fetchController = new AbortController();
    return fetchController.signal;
  }

  return {
    init: init,
    register: register,
    navigate: navigate,
    getCurrentRoute: getCurrentRoute,
    createSignal: createSignal,
    abortFetch: _abortPendingFetch
  };
})();