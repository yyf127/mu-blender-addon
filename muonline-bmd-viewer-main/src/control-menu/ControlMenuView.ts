import type { ViewerTab } from '../explorer-types';

const VIEW_BADGE: Record<ViewerTab, string> = {
  bmd: 'Model',
  character: 'Character',
  terrain: 'World',
  att: 'ATT Inspector',
  ozj: 'OZJ Browser',
  items: 'Item Browser',
  skills: 'Skill Browser',
  gfx: 'GFx Browser',
  sound: 'Sound Browser',
};

export function notifyViewportResize(): void {
  window.dispatchEvent(new Event('resize'));
}

function updateViewBadge(view: ViewerTab): void {
  const badge = document.getElementById('sidebar-view-badge');
  if (badge) {
    badge.textContent = VIEW_BADGE[view];
  }
}

export function scheduleViewportResize(resizeTimeoutRef: { current: number | null }): void {
  notifyViewportResize();
  window.requestAnimationFrame(notifyViewportResize);

  if (resizeTimeoutRef.current !== null) {
    window.clearTimeout(resizeTimeoutRef.current);
  }
  resizeTimeoutRef.current = window.setTimeout(notifyViewportResize, 320);
}

export function setActiveControlMenuView(target: ViewerTab): void {
  const tabButtons = document.querySelectorAll<HTMLButtonElement>('.tab-btn');
  const sidebarViews: Record<ViewerTab, HTMLElement | null> = {
    bmd: document.getElementById('sidebar-bmd'),
    character: document.getElementById('sidebar-character'),
    terrain: document.getElementById('sidebar-terrain'),
    att: document.getElementById('sidebar-att'),
    ozj: document.getElementById('sidebar-ozj'),
    items: document.getElementById('sidebar-items'),
    skills: document.getElementById('sidebar-skills'),
    gfx: document.getElementById('sidebar-gfx'),
    sound: document.getElementById('sidebar-sound'),
  };
  const mainViews: Record<ViewerTab, HTMLElement | null> = {
    bmd: document.getElementById('view-bmd'),
    character: document.getElementById('view-character'),
    terrain: document.getElementById('view-terrain'),
    att: document.getElementById('view-att'),
    ozj: document.getElementById('view-ozj'),
    items: document.getElementById('view-items'),
    skills: document.getElementById('view-skills'),
    gfx: document.getElementById('view-gfx'),
    sound: document.getElementById('view-sound'),
  };
  const statusElements: Record<ViewerTab, HTMLElement | null> = {
    bmd: document.getElementById('status'),
    character: document.getElementById('character-status'),
    terrain: document.getElementById('terrain-status-bar'),
    att: document.getElementById('att-status-bar'),
    ozj: document.getElementById('ozj-status-bar'),
    items: document.getElementById('items-status-bar'),
    skills: document.getElementById('skills-status-bar'),
    gfx: document.getElementById('gfx-status-bar'),
    sound: document.getElementById('sound-status-bar'),
  };

  tabButtons.forEach(button => {
    button.classList.toggle('active', button.dataset.view === target);
  });

  (Object.keys(sidebarViews) as ViewerTab[]).forEach(view => {
    sidebarViews[view]?.classList.toggle('hidden', view !== target);
    mainViews[view]?.classList.toggle('hidden', view !== target);
    statusElements[view]?.classList.toggle('hidden', view !== target);
  });

  updateViewBadge(target);
}
