import {
  buildHeightMinimapRaster,
  createWorldObjectId,
  minimapPointToWorld,
  worldToMinimapPoint,
} from '../src/terrain/TerrainExplorerUtils';

describe('TerrainExplorerUtils', () => {
  it('creates stable world object ids from world/type/position', () => {
    expect(createWorldObjectId(3, 17, { x: 128.1234, z: 512.9876 })).toBe('3:17:128.12:512.99');
  });

  it('maps world coordinates to minimap and back', () => {
    const point = worldToMinimapPoint(128, 768, 1024, 200, 200);
    expect(point).toEqual({ x: 25, y: 50 });

    const world = minimapPointToWorld(point.x, point.y, 200, 200, 1024);
    expect(world.x).toBeCloseTo(128, 5);
    expect(world.z).toBeCloseTo(768, 5);
  });

  it('builds an opaque minimap raster with height-based shading', () => {
    const raster = buildHeightMinimapRaster(
      new Float32Array([
        0, 0, 0,
        1, 10, 0,
        0, 20, 1,
        1, 30, 1,
      ]),
      new Float32Array([
        1, 1, 1,
        0.8, 0.8, 0.8,
        0.6, 0.6, 0.6,
        0.4, 0.4, 0.4,
      ]),
      2,
    );

    expect(raster.width).toBe(2);
    expect(raster.height).toBe(2);
    expect(raster.data).toHaveLength(16);
    expect(raster.data[3]).toBe(255);
    expect(raster.data[7]).toBe(255);
    expect(raster.data[11]).toBe(255);
    expect(raster.data[15]).toBe(255);

    const blueChannel = [
      raster.data[2],
      raster.data[6],
      raster.data[10],
      raster.data[14],
    ];
    expect(Math.min(...blueChannel)).toBeLessThan(Math.max(...blueChannel));
  });
});
