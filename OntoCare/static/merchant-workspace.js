/* Keep merchant tools inside one workspace without resetting the mail draft. */
(() => {
  const tabs = [...document.querySelectorAll('[data-workspace-tab]')];
  const panels = [...document.querySelectorAll('[data-workspace-panel]')];
  function select(id, focus = false) {
    if (!tabs.some(tab => tab.dataset.workspaceTab === id)) id = 'mail';
    for (const tab of tabs) {
      const active = tab.dataset.workspaceTab === id;
      tab.classList.toggle('active', active);
      tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
      if (active && focus) tab.focus();
    }
    for (const panel of panels) panel.hidden = panel.dataset.workspacePanel !== id;
    if (id === 'analytics') {
      const frame = document.getElementById('analyticsFrame');
      if (!frame.getAttribute('src')) frame.src = frame.dataset.src;
    }
  }
  function current() { return location.hash.slice(1) || 'mail'; }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => {
      if (current() !== tab.dataset.workspaceTab) location.hash = tab.dataset.workspaceTab;
      else select(current());
    });
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      location.hash = tabs[next].dataset.workspaceTab;
      select(tabs[next].dataset.workspaceTab, true);
    });
  });
  document.querySelectorAll('[data-open-workspace]').forEach(link => {
    link.addEventListener('click', event => {
      event.preventDefault();
      location.hash = link.dataset.openWorkspace;
      select(link.dataset.openWorkspace);
      document.getElementById('merchantTabs').scrollIntoView({block: 'nearest'});
    });
  });
  window.addEventListener('hashchange', () => select(current()));
  select(current());
})();
