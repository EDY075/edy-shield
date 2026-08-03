/**
 * EDY Shield Dashboard — Página Settings (M4.2)
 * Configura\u00e7\u00f5es do sistema + tema dark/light.
 */

Router.register('settings', {
  title: 'Settings',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>Settings</h1>' +
      '    <p>Configura\u00e7\u00f5es do EDY Shield</p>' +
      '  </div>' +
      '</div>' +
      '<div class="content-grid">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Apar\u00eancia</span></div>' +
      '    <div class="card-body">' +
      '      <div style="display: flex; flex-direction: column; gap: 16px;">' +
      '        <div>' +
      '          <label style="display: block; margin-bottom: 6px; font-size: 13px; color: var(--text-secondary);">Tema</label>' +
      '          <div style="display: flex; gap: 8px;">' +
      '            <button class="btn" id="themeDarkBtn" onclick="SettingsPage.setTheme(\'dark\')">Escuro</button>' +
      '            <button class="btn" id="themeLightBtn" onclick="SettingsPage.setTheme(\'light\')">Claro</button>' +
      '          </div>' +
      '        </div>' +
      '        <div>' +
      '          <label style="display: block; margin-bottom: 6px; font-size: 13px; color: var(--text-secondary);">Auto-refresh</label>' +
      '          <div style="display: flex; align-items: center; gap: 8px;">' +
      '            <input type="checkbox" id="autoRefreshToggle" checked onchange="SettingsPage.toggleAutoRefresh()" />' +
      '            <span style="font-size: 13px; color: var(--text-secondary);">Atualizar dados a cada 30 segundos</span>' +
      '          </div>' +
      '        </div>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alert Engine</span></div>' +
      '    <div class="card-body">' +
      '      <div style="display: flex; flex-direction: column; gap: 16px;">' +
      '        <div><label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-secondary);">Janela de Supress\u00e3o (s)</label><input class="settings-input" style="max-width: 100%; width: 100%;" value="300" /></div>' +
      '        <div><label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-secondary);">Severidade M\u00ednima</label><select class="settings-input" style="width: 100%;"><option>INFO</option><option>LOW</option><option selected>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></div>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '</div>' +
      '<div style="margin-top: 16px; display: flex; gap: 8px; justify-content: flex-end;">' +
      '  <button class="btn">Cancelar</button>' +
      '  <button class="btn btn-primary" onclick="Toast.success(\'Configura\u00e7\u00f5es salvas\')">Salvar</button>' +
      '</div>'
    );
  },
  onLoad: function () {
    SettingsPage._updateThemeButtons();
  },

  onUnload: function () {
    // N\u00e3o h\u00e1 timers ou fetch para limpar, mas garante consist\u00eancia
    if (Router.abortFetch) Router.abortFetch();
  }
});

var SettingsPage = {
  setTheme: function (theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('edy-shield-theme', theme);
    SettingsPage._updateThemeButtons();
    var icon = document.getElementById('themeToggleIcon');
    if (icon) icon.textContent = theme === 'dark' ? '\u2600' : '\uD83C\uDF19';
    Toast.info('Tema alterado para ' + (theme === 'dark' ? 'Escuro' : 'Claro'));
  },

  toggleAutoRefresh: function () {
    var toggle = document.getElementById('autoRefreshToggle');
    Toast.info('Auto-refresh: ' + (toggle.checked ? 'Ativado' : 'Desativado'));
  },

  _updateThemeButtons: function () {
    var current = document.documentElement.getAttribute('data-theme') || 'dark';
    var darkBtn = document.getElementById('themeDarkBtn');
    var lightBtn = document.getElementById('themeLightBtn');
    if (darkBtn && lightBtn) {
      if (current === 'dark') {
        darkBtn.classList.add('btn-primary');
        darkBtn.classList.remove('btn');
        lightBtn.classList.remove('btn-primary');
        lightBtn.classList.add('btn');
      } else {
        lightBtn.classList.add('btn-primary');
        lightBtn.classList.remove('btn');
        darkBtn.classList.remove('btn-primary');
        darkBtn.classList.add('btn');
      }
    }
  }
};