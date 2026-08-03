/**
 * EDY Shield Dashboard — Página Settings (M4.1)
 * Configurações do sistema.
 */

Router.register('settings', {
  title: 'Settings',
  render: function () {
    return (
      '<div class="page-header">' +
      '  <div class="page-header-left">' +
      '    <h1>Settings</h1>' +
      '    <p>Configurações do EDY Shield</p>' +
      '  </div>' +
      '</div>' +
      '<div class="content-grid">' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Geral</span></div>' +
      '    <div class="card-body">' +
      '      <div style="display: flex; flex-direction: column; gap: 16px;">' +
      '        <div><label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-secondary);">Host do Servidor</label><input class="topbar-search" style="max-width: 100%;" value="127.0.0.1" /></div>' +
      '        <div><label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-secondary);">Porta do Servidor</label><input class="topbar-search" style="max-width: 100%;" value="8000" /></div>' +
      '        <div><label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-secondary);">Banco SQLite</label><input class="topbar-search" style="max-width: 100%;" value="~/.edyshield/edy_shield.db" /></div>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '  <div class="card">' +
      '    <div class="card-header"><span class="card-title">Alert Engine</span></div>' +
      '    <div class="card-body">' +
      '      <div style="display: flex; flex-direction: column; gap: 16px;">' +
      '        <div><label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-secondary);">Janela de Supressão (s)</label><input class="topbar-search" style="max-width: 100%;" value="300" /></div>' +
      '        <div><label style="display: block; margin-bottom: 4px; font-size: 13px; color: var(--text-secondary);">Severidade Mínima</label><select class="btn" style="width: 100%;"><option>INFO</option><option>LOW</option><option selected>MEDIUM</option><option>HIGH</option><option>CRITICAL</option></select></div>' +
      '      </div>' +
      '    </div>' +
      '  </div>' +
      '</div>' +
      '<div style="margin-top: 16px; display: flex; gap: 8px; justify-content: flex-end;">' +
      '  <button class="btn">Cancelar</button>' +
      '  <button class="btn btn-primary" onclick="Toast.success(\'Configurações salvas (demo)\')">Salvar</button>' +
      '</div>'
    );
  }
});