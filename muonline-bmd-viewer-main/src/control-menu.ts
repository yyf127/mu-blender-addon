import type { ViewerTab } from './explorer-types';
import {
  DEFAULT_CONTROL_MENU_SECTIONS,
  setControlMenuSidebarCollapsed,
  toggleControlMenuSection,
  type ControlMenuSectionId,
} from './control-menu/ControlMenuState';
import {
  readControlMenuState,
  writeControlMenuState,
  type StorageLike,
} from './control-menu/ControlMenuStorage';
import {
  decorateSection,
  updateSectionUi,
} from './control-menu/ControlMenuSections';
import {
  notifyViewportResize,
  scheduleViewportResize,
  setActiveControlMenuView,
} from './control-menu/ControlMenuView';

export {
  DEFAULT_CONTROL_MENU_SECTIONS,
  createDefaultControlMenuState,
  mergeControlMenuState,
  setControlMenuSectionExpanded,
  setControlMenuSidebarCollapsed,
  toggleControlMenuSection,
  type ControlMenuSectionId,
  type ControlMenuState,
} from './control-menu/ControlMenuState';

interface InitControlMenuOptions {
  storage?: StorageLike;
}

export function initControlMenu(options: InitControlMenuOptions = {}): void {
  const sidebar = document.getElementById('sidebar');
  if (!sidebar) {
    return;
  }

  const storage = options.storage ?? window.localStorage;
  let state = readControlMenuState(storage);
  const resizeTimeoutRef: { current: number | null } = { current: null };

  const persist = (): void => {
    writeControlMenuState(storage, state);
  };

  const applySidebarState = (): void => {
    sidebar.classList.toggle('closed', state.sidebarCollapsed);
  };

  const applySectionState = (sectionId: ControlMenuSectionId): void => {
    const section = document.getElementById(sectionId);
    if (!section) {
      return;
    }

    decorateSection(section);
    updateSectionUi(section, state.sections[sectionId]);
  };

  const allSectionIds = Object.keys(DEFAULT_CONTROL_MENU_SECTIONS) as ControlMenuSectionId[];
  allSectionIds.forEach(sectionId => applySectionState(sectionId));
  applySidebarState();

  allSectionIds.forEach(sectionId => {
    const section = document.getElementById(sectionId);
    const toggle = section?.querySelector<HTMLButtonElement>(':scope > .control-section-toggle');
    toggle?.addEventListener('click', () => {
      state = toggleControlMenuSection(state, sectionId);
      applySectionState(sectionId);
      persist();
    });
  });

  const sidebarToggles = [
    document.getElementById('sidebar-toggle'),
    document.getElementById('character-sidebar-toggle'),
    document.getElementById('terrain-sidebar-toggle'),
  ].filter((value): value is HTMLElement => value instanceof HTMLElement);

  sidebarToggles.forEach(button => {
    button.addEventListener('click', () => {
      state = setControlMenuSidebarCollapsed(state, !state.sidebarCollapsed);
      applySidebarState();
      persist();
      scheduleViewportResize(resizeTimeoutRef);
    });
  });

  sidebar.addEventListener('transitionend', event => {
    if (event.target !== sidebar) {
      return;
    }

    if (event.propertyName !== 'transform' && event.propertyName !== 'margin-right') {
      return;
    }

    notifyViewportResize();
  });

  const tabButtons = document.querySelectorAll<HTMLButtonElement>('.tab-btn');
  tabButtons.forEach(button => {
    button.addEventListener('click', () => {
      const target = (button.dataset.view || 'bmd') as ViewerTab;
      setActiveControlMenuView(target);
      scheduleViewportResize(resizeTimeoutRef);
    });
  });

  setActiveControlMenuView('bmd');
}
