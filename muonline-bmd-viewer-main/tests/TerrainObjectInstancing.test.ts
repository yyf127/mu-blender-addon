import {
    getTerrainAnimatedInstancingModeForBackend,
    getTerrainObjectInstanceChunkKey,
    shouldChunkTerrainObjectInstances,
    TERRAIN_OBJECT_INSTANCE_CHUNK_WORLD_SIZE,
} from '../src/terrain/TerrainObjectInstancing';

describe('TerrainObjectInstancing', () => {
    it('uses small chunks so Object Distance culling does not keep large instanced regions visible', () => {
        expect(TERRAIN_OBJECT_INSTANCE_CHUNK_WORLD_SIZE).toBeLessThanOrEqual(1024);
        expect(getTerrainObjectInstanceChunkKey(0, 0)).toBe('0:0');
        expect(getTerrainObjectInstanceChunkKey(2048, 0)).toBe('2:0');
        expect(getTerrainObjectInstanceChunkKey(-1, -1)).toBe('-1:-1');
    });

    it('chunks every multi-instance object type so sparse objects do not span the full map', () => {
        expect(shouldChunkTerrainObjectInstances(1)).toBe(false);
        expect(shouldChunkTerrainObjectInstances(2)).toBe(true);
        expect(shouldChunkTerrainObjectInstances(8)).toBe(true);
    });

    it('avoids dynamic animated geometry uploads on WebGPU', () => {
        expect(getTerrainAnimatedInstancingModeForBackend('webgl')).toBe('dynamic');
        expect(getTerrainAnimatedInstancingModeForBackend('webgpu')).toBe('static-pose');
    });
});
