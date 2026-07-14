export interface ThumbnailQueueState {
    visibleIndexes: Set<number>;
    pendingIndexes: Set<number>;
}

export interface ThumbnailVisibilityEntry {
    index: number;
    isVisible: boolean;
    hasCachedThumbnail: boolean;
}

export interface ThumbnailVisibilityUpdate {
    state: ThumbnailQueueState;
    cachedIndexesToApply: number[];
}

export function applyThumbnailVisibilityEntries(
    state: ThumbnailQueueState,
    entries: ThumbnailVisibilityEntry[],
): ThumbnailVisibilityUpdate {
    const visibleIndexes = new Set(state.visibleIndexes);
    const pendingIndexes = new Set(state.pendingIndexes);
    const cachedIndexesToApply: number[] = [];

    for (const entry of entries) {
        if (entry.isVisible) {
            visibleIndexes.add(entry.index);
            if (entry.hasCachedThumbnail) {
                pendingIndexes.delete(entry.index);
                cachedIndexesToApply.push(entry.index);
            } else {
                pendingIndexes.add(entry.index);
            }
            continue;
        }

        visibleIndexes.delete(entry.index);
        pendingIndexes.delete(entry.index);
    }

    return {
        state: {
            visibleIndexes,
            pendingIndexes,
        },
        cachedIndexesToApply,
    };
}

export function getNextVisibleThumbnailIndex(state: ThumbnailQueueState): number | null {
    for (const index of state.pendingIndexes) {
        if (state.visibleIndexes.has(index)) {
            return index;
        }
    }

    return null;
}

export function removeThumbnailIndexFromQueue(
    state: ThumbnailQueueState,
    index: number,
): ThumbnailQueueState {
    const pendingIndexes = new Set(state.pendingIndexes);
    pendingIndexes.delete(index);

    return {
        visibleIndexes: new Set(state.visibleIndexes),
        pendingIndexes,
    };
}
