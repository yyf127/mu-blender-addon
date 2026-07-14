import {
  createDefaultControlMenuState,
  mergeControlMenuState,
  setControlMenuSectionExpanded,
  setControlMenuSidebarCollapsed,
  toggleControlMenuSection,
} from '../src/control-menu';

describe('control menu state helpers', () => {
  it('fills defaults and ignores malformed persisted values', () => {
    const merged = mergeControlMenuState({
      sidebarCollapsed: true,
      sections: {
        'bmd-import-section': false,
        'terrain-navigation-section': true,
        unknown: false,
      },
    });

    expect(merged.sidebarCollapsed).toBe(true);
    expect(merged.sections['bmd-import-section']).toBe(false);
    expect(merged.sections['terrain-navigation-section']).toBe(true);
    expect(merged.sections['terrain-attribute-section']).toBe(false);
    expect(merged.sections['character-profile-section']).toBe(true);
    expect(merged.sections['character-export-controls']).toBe(false);
    expect(Object.prototype.hasOwnProperty.call(merged.sections, 'unknown')).toBe(false);
  });

  it('returns a new state when toggling a known section', () => {
    const initial = createDefaultControlMenuState();
    const next = toggleControlMenuSection(initial, 'diagnostics-panel');

    expect(next).not.toBe(initial);
    expect(next.sections).not.toBe(initial.sections);
    expect(initial.sections['diagnostics-panel']).toBe(false);
    expect(next.sections['diagnostics-panel']).toBe(true);
  });

  it('ignores unknown sections and preserves the current state', () => {
    const initial = createDefaultControlMenuState();
    const next = setControlMenuSectionExpanded(initial, 'missing-section', true);

    expect(next).toBe(initial);
  });

  it('updates sidebar collapsed flag immutably', () => {
    const initial = createDefaultControlMenuState();
    const next = setControlMenuSidebarCollapsed(initial, true);

    expect(next.sidebarCollapsed).toBe(true);
    expect(initial.sidebarCollapsed).toBe(false);
  });
});
