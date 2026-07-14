export type TerrainObjectBlendModeName = 'Opaque' | 'Normal' | 'Additive' | 'Multiply' | 'Subtractive';

export interface TerrainObjectMaterialOverride {
    blending: TerrainObjectBlendModeName;
    alphaTest: number;
}

export interface TerrainObjectTypeOverride {
    materials: Record<string, TerrainObjectMaterialOverride>;
}

export interface TerrainObjectTransformOverride {
    position: {
        x: number;
        y: number;
        z: number;
    };
    rotation?: {
        x: number;
        y: number;
        z: number;
    };
    scale: number;
}

export interface TerrainWorldObjectOverrides {
    objects: Record<string, TerrainObjectTransformOverride>;
    objectTypes: Record<string, TerrainObjectTypeOverride>;
}

export interface TerrainObjectOverridesFile {
    version: 1;
    worlds: Record<string, TerrainWorldObjectOverrides>;
}

export const TERRAIN_OBJECT_OVERRIDES_VERSION = 1;
export const TERRAIN_OBJECT_BLEND_MODE_NAMES: TerrainObjectBlendModeName[] = [
    'Opaque',
    'Normal',
    'Additive',
    'Multiply',
    'Subtractive',
];

export function createEmptyTerrainObjectOverrides(): TerrainObjectOverridesFile {
    return {
        version: TERRAIN_OBJECT_OVERRIDES_VERSION,
        worlds: {},
    };
}

export function getTerrainObjectTypeOverride(
    overrides: TerrainObjectOverridesFile,
    worldNumber: number,
    objectType: number,
): TerrainObjectTypeOverride | null {
    return overrides.worlds[String(worldNumber)]?.objectTypes[String(objectType)] ?? null;
}

export function getTerrainObjectTransformOverride(
    overrides: TerrainObjectOverridesFile,
    worldNumber: number,
    objectId: string,
): TerrainObjectTransformOverride | null {
    return overrides.worlds[String(worldNumber)]?.objects[objectId] ?? null;
}

export function upsertTerrainObjectTypeOverride(
    overrides: TerrainObjectOverridesFile,
    worldNumber: number,
    objectType: number,
    typeOverride: TerrainObjectTypeOverride,
): TerrainObjectOverridesFile {
    const worldKey = String(worldNumber);
    const typeKey = String(objectType);
    const existingWorld = overrides.worlds[worldKey] ?? { objects: {}, objectTypes: {} };

    return {
        version: TERRAIN_OBJECT_OVERRIDES_VERSION,
        worlds: {
            ...overrides.worlds,
            [worldKey]: {
                objects: { ...existingWorld.objects },
                objectTypes: {
                    ...existingWorld.objectTypes,
                    [typeKey]: {
                        materials: { ...typeOverride.materials },
                    },
                },
            },
        },
    };
}

export function upsertTerrainObjectTransformOverride(
    overrides: TerrainObjectOverridesFile,
    worldNumber: number,
    objectId: string,
    transform: TerrainObjectTransformOverride,
): TerrainObjectOverridesFile {
    const worldKey = String(worldNumber);
    const existingWorld = overrides.worlds[worldKey] ?? { objects: {}, objectTypes: {} };

    return {
        version: TERRAIN_OBJECT_OVERRIDES_VERSION,
        worlds: {
            ...overrides.worlds,
            [worldKey]: {
                objects: {
                    ...existingWorld.objects,
                    [objectId]: {
                        position: { ...transform.position },
                        ...(transform.rotation ? { rotation: { ...transform.rotation } } : {}),
                        scale: transform.scale,
                    },
                },
                objectTypes: { ...existingWorld.objectTypes },
            },
        },
    };
}

export function removeTerrainObjectTypeOverride(
    overrides: TerrainObjectOverridesFile,
    worldNumber: number,
    objectType: number,
): TerrainObjectOverridesFile {
    const worldKey = String(worldNumber);
    const typeKey = String(objectType);
    const existingWorld = overrides.worlds[worldKey];
    if (!existingWorld?.objectTypes[typeKey]) {
        return overrides;
    }

    const nextObjectTypes = { ...existingWorld.objectTypes };
    delete nextObjectTypes[typeKey];

    const nextWorlds = { ...overrides.worlds };
    if (Object.keys(nextObjectTypes).length === 0 && Object.keys(existingWorld.objects).length === 0) {
        delete nextWorlds[worldKey];
    } else {
        nextWorlds[worldKey] = {
            objects: { ...existingWorld.objects },
            objectTypes: nextObjectTypes,
        };
    }

    return {
        version: TERRAIN_OBJECT_OVERRIDES_VERSION,
        worlds: nextWorlds,
    };
}

export function removeTerrainObjectTransformOverride(
    overrides: TerrainObjectOverridesFile,
    worldNumber: number,
    objectId: string,
): TerrainObjectOverridesFile {
    const worldKey = String(worldNumber);
    const existingWorld = overrides.worlds[worldKey];
    if (!existingWorld?.objects[objectId]) {
        return overrides;
    }

    const nextObjects = { ...existingWorld.objects };
    delete nextObjects[objectId];

    const nextWorlds = { ...overrides.worlds };
    if (Object.keys(nextObjects).length === 0 && Object.keys(existingWorld.objectTypes).length === 0) {
        delete nextWorlds[worldKey];
    } else {
        nextWorlds[worldKey] = {
            objects: nextObjects,
            objectTypes: { ...existingWorld.objectTypes },
        };
    }

    return {
        version: TERRAIN_OBJECT_OVERRIDES_VERSION,
        worlds: nextWorlds,
    };
}

export function normalizeTerrainObjectOverrides(value: unknown): TerrainObjectOverridesFile {
    if (!value || typeof value !== 'object') {
        return createEmptyTerrainObjectOverrides();
    }

    const source = value as {
        worlds?: unknown;
    };

    if (!source.worlds || typeof source.worlds !== 'object') {
        return createEmptyTerrainObjectOverrides();
    }

    const worlds: TerrainObjectOverridesFile['worlds'] = {};
    for (const [worldKey, worldValue] of Object.entries(source.worlds as Record<string, unknown>)) {
        if (!isNumericKey(worldKey) || !worldValue || typeof worldValue !== 'object') {
            continue;
        }

        const objects = normalizeObjectTransforms((worldValue as { objects?: unknown }).objects);
        const objectTypesSource = (worldValue as { objectTypes?: unknown }).objectTypes;
        const objectTypes = normalizeObjectTypes(objectTypesSource);

        if (Object.keys(objects).length > 0 || Object.keys(objectTypes).length > 0) {
            worlds[worldKey] = { objects, objectTypes };
        }
    }

    return {
        version: TERRAIN_OBJECT_OVERRIDES_VERSION,
        worlds,
    };
}

function normalizeObjectTypes(objectTypesSource: unknown): TerrainWorldObjectOverrides['objectTypes'] {
    if (!objectTypesSource || typeof objectTypesSource !== 'object') {
        return {};
    }

    const objectTypes: TerrainWorldObjectOverrides['objectTypes'] = {};
    for (const [typeKey, typeValue] of Object.entries(objectTypesSource as Record<string, unknown>)) {
        if (!isNumericKey(typeKey) || !typeValue || typeof typeValue !== 'object') {
            continue;
        }

        const materialsSource = (typeValue as { materials?: unknown }).materials;
        if (!materialsSource || typeof materialsSource !== 'object') {
            continue;
        }

        const materials: TerrainObjectTypeOverride['materials'] = {};
        for (const [materialKey, materialValue] of Object.entries(materialsSource as Record<string, unknown>)) {
            const normalized = normalizeMaterialOverride(materialValue);
            if (normalized) {
                materials[materialKey] = normalized;
            }
        }

        if (Object.keys(materials).length > 0) {
            objectTypes[typeKey] = { materials };
        }
    }

    return objectTypes;
}

function normalizeObjectTransforms(objectsSource: unknown): TerrainWorldObjectOverrides['objects'] {
    if (!objectsSource || typeof objectsSource !== 'object') {
        return {};
    }

    const objects: TerrainWorldObjectOverrides['objects'] = {};
    for (const [objectId, objectValue] of Object.entries(objectsSource as Record<string, unknown>)) {
        const normalized = normalizeObjectTransform(objectValue);
        if (objectId.trim() && normalized) {
            objects[objectId] = normalized;
        }
    }

    return objects;
}

function normalizeObjectTransform(value: unknown): TerrainObjectTransformOverride | null {
    if (!value || typeof value !== 'object') {
        return null;
    }

    const candidate = value as {
        position?: unknown;
        rotation?: unknown;
        scale?: unknown;
    };
    const position = candidate.position as { x?: unknown; y?: unknown; z?: unknown } | undefined;
    if (
        !position ||
        typeof position.x !== 'number' ||
        typeof position.y !== 'number' ||
        typeof position.z !== 'number' ||
        !Number.isFinite(position.x) ||
        !Number.isFinite(position.y) ||
        !Number.isFinite(position.z)
    ) {
        return null;
    }

    const scale = typeof candidate.scale === 'number' && Number.isFinite(candidate.scale)
        ? Math.max(0.01, candidate.scale)
        : 1;
    const rotation = normalizeVector3(candidate.rotation);

    return {
        position: {
            x: position.x,
            y: position.y,
            z: position.z,
        },
        ...(rotation ? { rotation } : {}),
        scale,
    };
}

function normalizeVector3(value: unknown): { x: number; y: number; z: number } | null {
    if (!value || typeof value !== 'object') {
        return null;
    }

    const candidate = value as { x?: unknown; y?: unknown; z?: unknown };
    if (
        typeof candidate.x !== 'number' ||
        typeof candidate.y !== 'number' ||
        typeof candidate.z !== 'number' ||
        !Number.isFinite(candidate.x) ||
        !Number.isFinite(candidate.y) ||
        !Number.isFinite(candidate.z)
    ) {
        return null;
    }

    return {
        x: candidate.x,
        y: candidate.y,
        z: candidate.z,
    };
}

function normalizeMaterialOverride(value: unknown): TerrainObjectMaterialOverride | null {
    if (!value || typeof value !== 'object') {
        return null;
    }

    const candidate = value as {
        blending?: unknown;
        alphaTest?: unknown;
    };
    if (
        typeof candidate.blending !== 'string' ||
        !TERRAIN_OBJECT_BLEND_MODE_NAMES.includes(candidate.blending as TerrainObjectBlendModeName)
    ) {
        return null;
    }

    const alphaTest = typeof candidate.alphaTest === 'number' && Number.isFinite(candidate.alphaTest)
        ? Math.max(0, Math.min(0.5, candidate.alphaTest))
        : 0;

    return {
        blending: candidate.blending as TerrainObjectBlendModeName,
        alphaTest,
    };
}

function isNumericKey(key: string): boolean {
    return /^\d+$/.test(key);
}
