import type { ExplorerVector3, SelectedWorldObjectRef } from '../explorer-types';

export function safeObject<T extends object>(value: unknown): Partial<T> {
  return value && typeof value === 'object' ? (value as Partial<T>) : {};
}

export function coerceNumber(value: unknown, fallback: number): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback;
}

export function coerceBoolean(value: unknown, fallback: boolean): boolean {
  return typeof value === 'boolean' ? value : fallback;
}

export function coerceString(value: unknown, fallback: string): string {
  return typeof value === 'string' ? value : fallback;
}

export function cloneState<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function mergeVector3(raw: unknown): ExplorerVector3 {
  const input = safeObject<ExplorerVector3>(raw);
  return {
    x: coerceNumber(input.x, 0),
    y: coerceNumber(input.y, 0),
    z: coerceNumber(input.z, 0),
  };
}

export function mergeSelectedObject(raw: unknown): SelectedWorldObjectRef | null {
  if (!raw || typeof raw !== 'object') {
    return null;
  }

  const input = raw as {
    objectId?: string;
    worldNumber?: number;
    type?: number;
    modelName?: unknown;
    modelFileKey?: unknown;
    displayName?: string;
    position?: unknown;
    rotation?: unknown;
    scale?: number;
  };

  return {
    objectId: coerceString(input.objectId, ''),
    worldNumber: coerceNumber(input.worldNumber, 0),
    type: coerceNumber(input.type, 0),
    modelName: typeof input.modelName === 'string' ? input.modelName : null,
    modelFileKey: typeof input.modelFileKey === 'string' ? input.modelFileKey : null,
    displayName: coerceString(input.displayName, 'Object'),
    position: mergeVector3(input.position),
    rotation: mergeVector3(input.rotation),
    scale: coerceNumber(input.scale, 1),
  };
}

export function mergeCollection<T>(
  raw: unknown,
  mapper: (value: unknown) => T | null,
  maxItems?: number,
): T[] {
  if (!Array.isArray(raw)) {
    return [];
  }

  const items = raw
    .map(mapper)
    .filter((value): value is T => value !== null);

  return typeof maxItems === 'number' ? items.slice(0, maxItems) : items;
}
