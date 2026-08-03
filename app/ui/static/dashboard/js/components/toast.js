/**
 * EDY Shield Dashboard — Toast Notification System (M4.1)
 *
 * Sistema de notificações não-bloqueante (toast) para feedback ao usuário.
 * Suporta 4 níveis: success, error, warning, info.
 *
 * Uso:
 *   Toast.show({ type: 'success', title: 'OK', message: 'Operação concluída' });
 *   Toast.success('Operação concluída');
 *   Toast.error('Falha ao carregar dados');
 */

var Toast = (function () {
  'use strict';

  var container = null;
  var DEFAULT_DURATION = 4000;

  function _getContainer() {
    if (!container) {
      container = document.getElementById('toastContainer');
      if (!container) {
        container = document.createElement('div');
        container.className = 'toast-container';
        container.id = 'toastContainer';
        document.body.appendChild(container);
      }
    }
    return container;
  }

  function _createIcon(type) {
    var icons = {
      success: '\u2713',
      error: '\u2717',
      warning: '\u26A0',
      info: '\u2139'
    };
    return icons[type] || icons.info;
  }

  function show(options) {
    var opts = options || {};
    var type = opts.type || 'info';
    var title = opts.title || '';
    var message = opts.message || '';
    var duration = opts.duration !== undefined ? opts.duration : DEFAULT_DURATION;

    var toast = document.createElement('div');
    toast.className = 'toast ' + type;

    var iconSpan = document.createElement('span');
    iconSpan.className = 'toast-icon';
    iconSpan.textContent = _createIcon(type);

    var content = document.createElement('div');
    content.className = 'toast-content';

    if (title) {
      var titleEl = document.createElement('div');
      titleEl.className = 'toast-title';
      titleEl.textContent = title;
      content.appendChild(titleEl);
    }
    if (message) {
      var msgEl = document.createElement('div');
      msgEl.className = 'toast-message';
      msgEl.textContent = message;
      content.appendChild(msgEl);
    }

    var closeBtn = document.createElement('button');
    closeBtn.className = 'toast-close';
    closeBtn.innerHTML = '&times;';
    closeBtn.onclick = function () { _remove(toast); };

    toast.appendChild(iconSpan);
    toast.appendChild(content);
    toast.appendChild(closeBtn);

    _getContainer().appendChild(toast);

    if (duration > 0) {
      setTimeout(function () { _remove(toast); }, duration);
    }

    return toast;
  }

  function _remove(toast) {
    if (!toast || !toast.parentNode) return;
    toast.classList.add('removing');
    setTimeout(function () {
      if (toast.parentNode) toast.parentNode.removeChild(toast);
    }, 200);
  }

  return {
    show: show,
    success: function (message, title) { show({ type: 'success', message: message, title: title }); },
    error: function (message, title) { show({ type: 'error', message: message, title: title }); },
    warning: function (message, title) { show({ type: 'warning', message: message, title: title }); },
    info: function (message, title) { show({ type: 'info', message: message, title: title }); }
  };
})();