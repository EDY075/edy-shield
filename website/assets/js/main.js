/* ═══════════════════════════════════════════════════════════════
   EDY SHIELD — Website oficial (Fase 2)
   JS leve (< 4KB): menu mobile, tabs de instalação, reveal on scroll
   Sem dependências externas. Performance-first.
   ═══════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  /* ------------------------------------------------------------
     1. Menu mobile (navbar toggle)
     ------------------------------------------------------------ */
  var toggle = document.getElementById('nav-toggle');
  var menu = document.getElementById('mobile-menu');

  if (toggle && menu) {
    toggle.addEventListener('click', function () {
      var open = menu.hasAttribute('hidden');
      menu.hidden = !open;
      toggle.setAttribute('aria-expanded', String(open));
      toggle.setAttribute('aria-label', open ? 'Fechar menu' : 'Abrir menu');
    });

    // Fecha o menu ao clicar em qualquer link interno
    menu.querySelectorAll('a').forEach(function (link) {
      link.addEventListener('click', function () {
        menu.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
      });
    });
  }

  /* ------------------------------------------------------------
     2. Tabs de instalação
     ------------------------------------------------------------ */
  var tabs = Array.prototype.slice.call(document.querySelectorAll('.install-tab'));
  tabs.forEach(function (tab) {
    tab.addEventListener('click', function () {
      tabs.forEach(function (t) {
        var active = t === tab;
        t.classList.toggle('is-active', active);
        t.setAttribute('aria-selected', String(active));
        t.setAttribute('tabindex', active ? '0' : '-1');
      });
      var panelId = tab.getAttribute('aria-controls');
      var panel = document.getElementById(panelId);
      if (panel) panel.hidden = false;
      tabs.forEach(function (t) {
        var otherId = t.getAttribute('aria-controls');
        if (otherId !== panelId) {
          var other = document.getElementById(otherId);
          if (other) other.hidden = true;
        }
      });
    });
  });

  /* ------------------------------------------------------------
     3. Reveal on scroll — discreto, apenas se suportado
     ------------------------------------------------------------ */
  if ('IntersectionObserver' in window) {
    var reveal = document.querySelectorAll('.feature-card, .arch-principle, .roadmap__item');
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.style.opacity = '1';
          entry.target.style.transform = 'none';
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.08 });

    reveal.forEach(function (el) {
      el.style.opacity = '0';
      el.style.transform = 'translateY(8px)';
      el.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
      observer.observe(el);
    });
  }

  /* ------------------------------------------------------------
     4. Navbar — estado ao rolar (borda mais forte)
     ------------------------------------------------------------ */
  var navbar = document.getElementById('navbar');
  if (navbar) {
    var onScroll = function () {
      navbar.style.boxShadow = window.scrollY > 8
        ? '0 1px 0 rgba(255,255,255,0.04)'
        : 'none';
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }
})();
