import type {
  BmdSessionState,
  CharacterPreset,
  CharacterSessionState,
  ExplorerBookmark,
  RecentBookmarkEntry,
  RecentModelEntry,
  RecentWorldEntry,
  TerrainSessionState,
  ViewerSessionState,
  ViewerTab,
} from '../explorer-types';
import {
  MAX_RECENT_BOOKMARKS,
  MAX_RECENT_MODELS,
  MAX_RECENT_WORLDS,
  STORAGE_KEY,
} from './constants';
import { createDefaultViewerSessionState } from './defaults';
import { cloneState } from './helpers';
import { mergeViewerSessionState } from './merge';

export interface StorageLike {
  getItem(key: string): string | null;
  setItem(key: string, value: string): void;
}

function sortCharacterPresets(presets: CharacterPreset[]): CharacterPreset[] {
  presets.sort((a, b) => {
    if (a.pinned !== b.pinned) {
      return a.pinned ? -1 : 1;
    }

    return a.name.localeCompare(b.name);
  });

  return presets;
}

function pushUniqueRecentEntry<T>(
  items: T[],
  entry: T,
  isSameEntry: (item: T) => boolean,
  maxItems: number,
): T[] {
  return [entry, ...items.filter(item => !isSameEntry(item))].slice(0, maxItems);
}

export class ExplorerStateStore {
  private readonly key: string;
  private readonly storage: StorageLike | null;
  private state: ViewerSessionState;
  private readonly listeners = new Set<(state: ViewerSessionState) => void>();

  constructor(storage: StorageLike | null = typeof window !== 'undefined' ? window.localStorage : null, key = STORAGE_KEY) {
    this.storage = storage;
    this.key = key;
    this.state = this.load();
  }

  getState(): ViewerSessionState {
    return cloneState(this.state);
  }

  subscribe(listener: (state: ViewerSessionState) => void): () => void {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  }

  setActiveView(activeView: ViewerTab): void {
    this.update(state => {
      state.activeView = activeView;
    });
  }

  setPresentationMode(enabled: boolean): void {
    this.update(state => {
      state.presentationMode = enabled;
    });
  }

  setTerrainState(terrain: TerrainSessionState): void {
    this.update(state => {
      state.terrain = cloneState(terrain);
    });
  }

  setCharacterState(character: CharacterSessionState): void {
    this.update(state => {
      state.character = cloneState(character);
    });
  }

  setBmdState(bmd: BmdSessionState): void {
    this.update(state => {
      state.bmd = cloneState(bmd);
    });
  }

  upsertBookmark(bookmark: ExplorerBookmark): void {
    this.update(state => {
      const index = state.bookmarks.findIndex(item => item.id === bookmark.id);
      if (index >= 0) {
        state.bookmarks[index] = cloneState(bookmark);
      } else {
        state.bookmarks.unshift(cloneState(bookmark));
      }

      state.bookmarks.sort((a, b) => b.updatedAt - a.updatedAt);
    });
  }

  renameBookmark(bookmarkId: string, name: string): void {
    this.update(state => {
      const bookmark = state.bookmarks.find(item => item.id === bookmarkId);
      if (!bookmark) {
        return;
      }

      bookmark.name = name;
      bookmark.updatedAt = Date.now();
      state.recentBookmarks.forEach(entry => {
        if (entry.bookmarkId === bookmarkId) {
          entry.label = name;
        }
      });
    });
  }

  deleteBookmark(bookmarkId: string): void {
    this.update(state => {
      state.bookmarks = state.bookmarks.filter(item => item.id !== bookmarkId);
      state.recentBookmarks = state.recentBookmarks.filter(item => item.bookmarkId !== bookmarkId);
    });
  }

  upsertCharacterPreset(preset: CharacterPreset): void {
    this.update(state => {
      const index = state.characterPresets.findIndex(item => item.id === preset.id);
      if (index >= 0) {
        state.characterPresets[index] = cloneState(preset);
      } else {
        state.characterPresets.push(cloneState(preset));
      }

      sortCharacterPresets(state.characterPresets);
    });
  }

  toggleCharacterPresetPinned(presetId: string): void {
    this.update(state => {
      const preset = state.characterPresets.find(item => item.id === presetId);
      if (!preset) {
        return;
      }

      preset.pinned = !preset.pinned;
      preset.updatedAt = Date.now();
      sortCharacterPresets(state.characterPresets);
    });
  }

  deleteCharacterPreset(presetId: string): void {
    this.update(state => {
      state.characterPresets = state.characterPresets.filter(item => item.id !== presetId);
    });
  }

  pushRecentWorld(entry: RecentWorldEntry): void {
    this.update(state => {
      state.recentWorlds = pushUniqueRecentEntry(
        state.recentWorlds,
        entry,
        item => item.worldNumber === entry.worldNumber,
        MAX_RECENT_WORLDS,
      );
    });
  }

  pushRecentBookmark(entry: RecentBookmarkEntry): void {
    this.update(state => {
      state.recentBookmarks = pushUniqueRecentEntry(
        state.recentBookmarks,
        entry,
        item => item.bookmarkId === entry.bookmarkId,
        MAX_RECENT_BOOKMARKS,
      );
    });
  }

  pushRecentModel(entry: RecentModelEntry): void {
    this.update(state => {
      state.recentModels = pushUniqueRecentEntry(
        state.recentModels,
        entry,
        item => item.label === entry.label && item.modelFileKey === entry.modelFileKey,
        MAX_RECENT_MODELS,
      );
    });
  }

  update(mutator: (state: ViewerSessionState) => void): void {
    const nextState = cloneState(this.state);
    mutator(nextState);
    this.state = mergeViewerSessionState(nextState);
    this.persist();
    this.emit();
  }

  private load(): ViewerSessionState {
    if (!this.storage) {
      return createDefaultViewerSessionState();
    }

    try {
      const raw = this.storage.getItem(this.key);
      if (!raw) {
        return createDefaultViewerSessionState();
      }

      return mergeViewerSessionState(JSON.parse(raw));
    } catch {
      return createDefaultViewerSessionState();
    }
  }

  private persist(): void {
    if (!this.storage) {
      return;
    }

    this.storage.setItem(this.key, JSON.stringify(this.state));
  }

  private emit(): void {
    const snapshot = this.getState();
    this.listeners.forEach(listener => listener(snapshot));
  }
}
