export const TERRAIN_OBJECT_INSTANCE_CHUNK_WORLD_SIZE = 1024;

export type TerrainRendererBackend = 'webgl' | 'webgpu';
export type TerrainAnimatedInstancingMode = 'dynamic' | 'static-pose';

export function getTerrainAnimatedInstancingModeForBackend(
    backend: TerrainRendererBackend,
): TerrainAnimatedInstancingMode {
    return backend === 'webgpu' ? 'static-pose' : 'dynamic';
}

export function shouldChunkTerrainObjectInstances(instanceCount: number): boolean {
    return instanceCount > 1;
}

export function getTerrainObjectInstanceChunkKey(worldX: number, worldZ: number): string {
    const chunkX = Math.floor(worldX / TERRAIN_OBJECT_INSTANCE_CHUNK_WORLD_SIZE);
    const chunkZ = Math.floor(worldZ / TERRAIN_OBJECT_INSTANCE_CHUNK_WORLD_SIZE);
    return `${chunkX}:${chunkZ}`;
}
