import {
  applyThumbnailVisibilityEntries,
  getNextVisibleThumbnailIndex,
  removeThumbnailIndexFromQueue,
} from '../src/utils/FolderThumbnailQueue';

describe('FolderThumbnailQueue', () => {
  it('queues only visible thumbnails without cached previews', () => {
    const initial = {
      visibleIndexes: new Set<number>(),
      pendingIndexes: new Set<number>([2]),
    };

    const update = applyThumbnailVisibilityEntries(initial, [
      { index: 0, isVisible: true, hasCachedThumbnail: false },
      { index: 1, isVisible: true, hasCachedThumbnail: true },
      { index: 2, isVisible: false, hasCachedThumbnail: false },
    ]);

    expect(update.state.visibleIndexes).toEqual(new Set([0, 1]));
    expect(update.state.pendingIndexes).toEqual(new Set([0]));
    expect(update.cachedIndexesToApply).toEqual([1]);
    expect(initial.visibleIndexes).toEqual(new Set());
    expect(initial.pendingIndexes).toEqual(new Set([2]));
  });

  it('returns the next queued thumbnail only while it is still visible', () => {
    expect(getNextVisibleThumbnailIndex({
      visibleIndexes: new Set([3]),
      pendingIndexes: new Set([2, 3]),
    })).toBe(3);

    expect(getNextVisibleThumbnailIndex({
      visibleIndexes: new Set([3]),
      pendingIndexes: new Set([2]),
    })).toBeNull();
  });

  it('removes a processed thumbnail without mutating the previous queue state', () => {
    const initial = {
      visibleIndexes: new Set([0, 1]),
      pendingIndexes: new Set([0, 1]),
    };

    const next = removeThumbnailIndexFromQueue(initial, 0);

    expect(next.visibleIndexes).toEqual(new Set([0, 1]));
    expect(next.pendingIndexes).toEqual(new Set([1]));
    expect(initial.pendingIndexes).toEqual(new Set([0, 1]));
  });
});
