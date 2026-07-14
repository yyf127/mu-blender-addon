import {
  createDefaultControlMenuState,
  mergeControlMenuState,
  type ControlMenuState,
} from './ControlMenuState';

const CONTROL_MENU_STORAGE_KEY = 'bmd-viewer-control-menu-state';

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

export function readControlMenuState(storage: StorageLike): ControlMenuState {
  try {
    const rawValue = storage.getItem(CONTROL_MENU_STORAGE_KEY);
    if (!rawValue) {
      return createDefaultControlMenuState();
    }

    return mergeControlMenuState(JSON.parse(rawValue));
  } catch {
    return createDefaultControlMenuState();
  }
}

export function writeControlMenuState(storage: StorageLike, state: ControlMenuState): void {
  storage.setItem(CONTROL_MENU_STORAGE_KEY, JSON.stringify(state));
}
