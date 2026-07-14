import {
  ExplorerStateStore,
  createDefaultViewerSessionState,
  mergeViewerSessionState,
} from '../src/explorer-store';

class MemoryStorage {
  private readonly store = new Map<string, string>();

  getItem(key: string): string | null {
    return this.store.get(key) ?? null;
  }

  setItem(key: string, value: string): void {
    this.store.set(key, value);
  }
}

describe('mergeViewerSessionState', () => {
  it('fills defaults for missing and invalid values', () => {
    const merged = mergeViewerSessionState({
      activeView: 'terrain',
      presentationMode: true,
      terrain: {
        rendererBackend: 'webgpu',
        lastWorldNumber: 7,
        availableWorldNumbers: [7, 'bad', 8],
        selectedObject: {
          objectId: 'obj-1',
          worldNumber: 7,
          type: 12,
          displayName: 'Tree',
          position: { x: 10, z: 20 },
          rotation: { y: 45 },
        },
      },
      character: {
        classValue: 203,
        equipment: { helm: '7:12' },
      },
      bmd: {
        rendererBackend: 'webgpu',
        lastModelName: 'Tree01.bmd',
      },
    });

    expect(merged.activeView).toBe('terrain');
    expect(merged.presentationMode).toBe(true);
    expect(merged.terrain.lastWorldNumber).toBe(7);
    expect(merged.terrain.rendererBackend).toBe('webgpu');
    expect(merged.terrain.availableWorldNumbers).toEqual([7, 8]);
    expect(merged.terrain.selectedObject).toEqual({
      objectId: 'obj-1',
      worldNumber: 7,
      type: 12,
      modelName: null,
      modelFileKey: null,
      displayName: 'Tree',
      position: { x: 10, y: 0, z: 20 },
      rotation: { x: 0, y: 45, z: 0 },
      scale: 1,
    });
    expect(merged.character.classValue).toBe(203);
    expect(merged.character.equipment.helm).toBe('7:12');
    expect(merged.character.equipment.armor).toBe('');
    expect(merged.bmd.lastModelName).toBe('Tree01.bmd');
    expect(merged.bmd.rendererBackend).toBe('webgpu');
    expect(merged.terrain.animationsEnabled).toBe(true);
    expect(merged.bmd.animationsEnabled).toBe(true);
  });

  it('drops malformed collections instead of crashing', () => {
    const merged = mergeViewerSessionState({
      bookmarks: [{ broken: true }],
      recentWorlds: [{ label: 'bad' }],
      recentBookmarks: [{ label: 'bad' }],
      recentModels: [{ timestamp: 1 }],
      characterPresets: [{ id: 'preset-1' }],
    });

    const defaults = createDefaultViewerSessionState();
    expect(merged.bookmarks).toEqual(defaults.bookmarks);
    expect(merged.recentWorlds).toEqual(defaults.recentWorlds);
    expect(merged.recentBookmarks).toEqual(defaults.recentBookmarks);
    expect(merged.recentModels).toEqual(defaults.recentModels);
    expect(merged.characterPresets).toEqual(defaults.characterPresets);
  });

  it('merges animation toggles with sane defaults', () => {
    const merged = mergeViewerSessionState({
      terrain: {
        animationsEnabled: false,
      },
      bmd: {
        animationsEnabled: false,
      },
    });

    expect(merged.terrain.animationsEnabled).toBe(false);
    expect(merged.bmd.animationsEnabled).toBe(false);
  });

  it('normalizes bookmark selected object vectors and optional fields', () => {
    const merged = mergeViewerSessionState({
      bookmarks: [{
        id: 'bookmark-1',
        name: 'Spawn',
        worldNumber: 3,
        cameraPosition: { x: 1 },
        cameraTarget: { z: 9 },
        selectedObject: {
          objectId: 'tree-1',
          worldNumber: 3,
          type: 7,
          displayName: 'Tree',
          position: { x: 10, z: 20 },
          rotation: { y: 45 },
        },
      }],
    });

    expect(merged.bookmarks).toHaveLength(1);
    expect(merged.bookmarks[0].cameraPosition).toEqual({ x: 1, y: 0, z: 0 });
    expect(merged.bookmarks[0].cameraTarget).toEqual({ x: 0, y: 0, z: 9 });
    expect(merged.bookmarks[0].selectedObject).toEqual({
      objectId: 'tree-1',
      worldNumber: 3,
      type: 7,
      modelName: null,
      modelFileKey: null,
      displayName: 'Tree',
      position: { x: 10, y: 0, z: 20 },
      rotation: { x: 0, y: 45, z: 0 },
      scale: 1,
    });
  });
});

describe('ExplorerStateStore', () => {
  it('deduplicates recents and persists bookmark renames', () => {
    const storage = new MemoryStorage();
    const store = new ExplorerStateStore(storage);

    store.upsertBookmark({
      id: 'bookmark-1',
      name: 'Lorencia Gate',
      worldNumber: 0,
      cameraPosition: { x: 10, y: 20, z: 30 },
      cameraTarget: { x: 12, y: 0, z: 18 },
      selectedObject: null,
      createdAt: 1,
      updatedAt: 1,
    });
    store.pushRecentBookmark({
      bookmarkId: 'bookmark-1',
      label: 'Lorencia Gate',
      timestamp: 100,
    });
    store.pushRecentBookmark({
      bookmarkId: 'bookmark-1',
      label: 'Lorencia Gate',
      timestamp: 150,
    });
    store.pushRecentWorld({
      worldNumber: 0,
      label: 'World 0',
      timestamp: 10,
    });
    store.pushRecentWorld({
      worldNumber: 0,
      label: 'World 0',
      timestamp: 20,
    });
    store.renameBookmark('bookmark-1', 'Lorencia Spawn');

    const snapshot = store.getState();
    expect(snapshot.recentBookmarks).toHaveLength(1);
    expect(snapshot.recentBookmarks[0]).toEqual({
      bookmarkId: 'bookmark-1',
      label: 'Lorencia Spawn',
      timestamp: 150,
    });
    expect(snapshot.recentWorlds).toHaveLength(1);
    expect(snapshot.recentWorlds[0].timestamp).toBe(20);
    expect(snapshot.bookmarks[0].name).toBe('Lorencia Spawn');

    const restored = new ExplorerStateStore(storage).getState();
    expect(restored.bookmarks[0].name).toBe('Lorencia Spawn');
    expect(restored.recentBookmarks[0].label).toBe('Lorencia Spawn');
  });

  it('falls back to defaults when persisted state is invalid json', () => {
    const storage = new MemoryStorage();
    storage.setItem('broken-state', '{invalid-json');

    const store = new ExplorerStateStore(storage, 'broken-state');

    expect(store.getState()).toEqual(createDefaultViewerSessionState());
  });

  it('enforces recent entry limits while keeping newest entries first', () => {
    const store = new ExplorerStateStore(new MemoryStorage());

    for (let index = 0; index < 12; index += 1) {
      store.pushRecentWorld({
        worldNumber: index,
        label: `World ${index}`,
        timestamp: index,
      });
      store.pushRecentBookmark({
        bookmarkId: `bookmark-${index}`,
        label: `Bookmark ${index}`,
        timestamp: index,
      });
      store.pushRecentModel({
        label: `Model ${index}`,
        modelFileKey: `model-${index}.bmd`,
        sourceWorldNumber: index,
        timestamp: index,
      });
    }

    const snapshot = store.getState();

    expect(snapshot.recentWorlds).toHaveLength(8);
    expect(snapshot.recentWorlds[0].worldNumber).toBe(11);
    expect(snapshot.recentWorlds.at(-1)?.worldNumber).toBe(4);

    expect(snapshot.recentBookmarks).toHaveLength(10);
    expect(snapshot.recentBookmarks[0].bookmarkId).toBe('bookmark-11');
    expect(snapshot.recentBookmarks.at(-1)?.bookmarkId).toBe('bookmark-2');

    expect(snapshot.recentModels).toHaveLength(10);
    expect(snapshot.recentModels[0].label).toBe('Model 11');
    expect(snapshot.recentModels.at(-1)?.label).toBe('Model 2');
  });

  it('sorts character presets by pinned status and name', () => {
    const store = new ExplorerStateStore(new MemoryStorage());

    store.upsertCharacterPreset({
      id: 'preset-z',
      name: 'Zulu',
      pinned: false,
      createdAt: 1,
      updatedAt: 1,
      ...createDefaultViewerSessionState().character,
    });
    store.upsertCharacterPreset({
      id: 'preset-a',
      name: 'Alpha',
      pinned: true,
      createdAt: 2,
      updatedAt: 2,
      ...createDefaultViewerSessionState().character,
    });
    store.upsertCharacterPreset({
      id: 'preset-m',
      name: 'Mike',
      pinned: false,
      createdAt: 3,
      updatedAt: 3,
      ...createDefaultViewerSessionState().character,
    });

    expect(store.getState().characterPresets.map(preset => preset.name)).toEqual([
      'Alpha',
      'Mike',
      'Zulu',
    ]);

    store.toggleCharacterPresetPinned('preset-z');

    expect(store.getState().characterPresets.map(preset => `${preset.pinned}:${preset.name}`)).toEqual([
      'true:Alpha',
      'true:Zulu',
      'false:Mike',
    ]);
  });

  it('returns detached snapshots from getState', () => {
    const store = new ExplorerStateStore(new MemoryStorage());
    const snapshot = store.getState();

    snapshot.terrain.availableWorldNumbers.push(99);
    snapshot.character.equipment.helm = 'mutated';

    const freshSnapshot = store.getState();
    expect(freshSnapshot.terrain.availableWorldNumbers).toEqual([]);
    expect(freshSnapshot.character.equipment.helm).toBe('');
  });
});
