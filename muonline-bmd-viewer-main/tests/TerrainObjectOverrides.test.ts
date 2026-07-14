import {
  createEmptyTerrainObjectOverrides,
  getTerrainObjectTransformOverride,
  getTerrainObjectTypeOverride,
  normalizeTerrainObjectOverrides,
  removeTerrainObjectTransformOverride,
  removeTerrainObjectTypeOverride,
  upsertTerrainObjectTransformOverride,
  upsertTerrainObjectTypeOverride,
} from '../src/terrain/TerrainObjectOverrides';

describe('TerrainObjectOverrides', () => {
  it('upserts and removes per-world per-type material settings immutably', () => {
    const empty = createEmptyTerrainObjectOverrides();
    const saved = upsertTerrainObjectTypeOverride(empty, 1, 23, {
      materials: {
        mesh_1: { blending: 'Normal', alphaTest: 0.24 },
      },
    });

    expect(empty.worlds).toEqual({});
    expect(getTerrainObjectTypeOverride(saved, 1, 23)?.materials.mesh_1).toEqual({
      blending: 'Normal',
      alphaTest: 0.24,
    });

    const removed = removeTerrainObjectTypeOverride(saved, 1, 23);
    expect(getTerrainObjectTypeOverride(removed, 1, 23)).toBeNull();
    expect(removed.worlds).toEqual({});
  });

  it('upserts and removes per-object transforms', () => {
    const saved = upsertTerrainObjectTransformOverride(
      createEmptyTerrainObjectOverrides(),
      1,
      '1:23:14700.00:13100.00',
      {
        position: { x: 14710, y: 165, z: 13120 },
        rotation: { x: 0, y: 90, z: 15 },
        scale: 1.25,
      },
    );

    expect(getTerrainObjectTransformOverride(saved, 1, '1:23:14700.00:13100.00')).toEqual({
      position: { x: 14710, y: 165, z: 13120 },
      rotation: { x: 0, y: 90, z: 15 },
      scale: 1.25,
    });

    expect(removeTerrainObjectTransformOverride(saved, 1, '1:23:14700.00:13100.00').worlds).toEqual({});
  });

  it('normalizes persisted JSON and drops malformed entries', () => {
    const normalized = normalizeTerrainObjectOverrides({
      version: 99,
      worlds: {
        1: {
          objects: {
            '1:23:14700.00:13100.00': {
              position: { x: 14710, y: 165, z: 13120 },
              rotation: { x: 0, y: 90, z: 15 },
              scale: 1.25,
            },
            malformed: {
              position: { x: 'bad', y: 0, z: 0 },
              scale: 1,
            },
          },
          objectTypes: {
            23: {
              materials: {
                mesh_1: { blending: 'Additive', alphaTest: 2 },
                mesh_2: { blending: 'Unknown', alphaTest: 0.2 },
              },
            },
            bad: {
              materials: {
                mesh_3: { blending: 'Opaque', alphaTest: 0 },
              },
            },
          },
        },
      },
      unrelated: true,
    });

    expect(normalized).toEqual({
      version: 1,
      worlds: {
        1: {
          objects: {
            '1:23:14700.00:13100.00': {
              position: { x: 14710, y: 165, z: 13120 },
              rotation: { x: 0, y: 90, z: 15 },
              scale: 1.25,
            },
          },
          objectTypes: {
            23: {
              materials: {
                mesh_1: { blending: 'Additive', alphaTest: 0.5 },
              },
            },
          },
        },
      },
    });
  });
});
