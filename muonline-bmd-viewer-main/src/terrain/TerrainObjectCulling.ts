import * as THREE from 'three';

export interface TerrainObjectDrawRangeSphere {
    center: THREE.Vector3;
    radius: number;
}

export class TerrainObjectCullingIndex {
    private buckets = new Map<string, THREE.Object3D[]>();
    private fallbacks: THREE.Object3D[] = [];
    private visible = new Set<THREE.Object3D>();
    private maxRadius = 0;
    private readonly tempCenter = new THREE.Vector3();
    private readonly tempScale = new THREE.Vector3();

    clear(): void {
        this.buckets = new Map();
        this.fallbacks = [];
        this.visible.clear();
        this.maxRadius = 0;
    }

    rebuild(objects: Iterable<THREE.Object3D>): void {
        this.clear();

        for (const object of objects) {
            const { radius } = getTerrainObjectDrawRangeSphere(object, this.tempCenter, this.tempScale);
            this.maxRadius = Math.max(this.maxRadius, radius);
            object.visible = false;

            const chunkKey = object.userData.terrainObjectChunkKey as string | undefined;
            if (chunkKey) {
                const bucket = this.buckets.get(chunkKey);
                if (bucket) {
                    bucket.push(object);
                } else {
                    this.buckets.set(chunkKey, [object]);
                }
                continue;
            }

            this.fallbacks.push(object);
        }
    }

    collectCandidates(
        cameraPosition: THREE.Vector3,
        drawDistance: number,
        chunkSize: number,
    ): Set<THREE.Object3D> {
        const candidates = new Set<THREE.Object3D>(this.fallbacks);
        const range = drawDistance + this.maxRadius;
        const keys = getTerrainObjectCullingChunkKeys(
            cameraPosition.x,
            cameraPosition.z,
            range,
            chunkSize,
        );

        for (const key of keys) {
            const bucket = this.buckets.get(key);
            if (!bucket) continue;
            for (const object of bucket) {
                candidates.add(object);
            }
        }

        for (const object of this.visible) {
            candidates.add(object);
        }

        return candidates;
    }

    clearVisible(): void {
        this.visible.clear();
    }

    addVisible(object: THREE.Object3D): void {
        this.visible.add(object);
    }

    replaceVisible(objects: Set<THREE.Object3D>): void {
        this.visible = objects;
    }

    forEachVisible(callback: (object: THREE.Object3D) => void): void {
        this.visible.forEach(callback);
    }
}

export function getTerrainObjectCullingChunkKeys(
    worldX: number,
    worldZ: number,
    range: number,
    chunkSize: number,
): string[] {
    const safeRange = Math.max(0, range);
    const startX = Math.floor((worldX - safeRange) / chunkSize);
    const endX = Math.floor((worldX + safeRange) / chunkSize);
    const startZ = Math.floor((worldZ - safeRange) / chunkSize);
    const endZ = Math.floor((worldZ + safeRange) / chunkSize);
    const keys: string[] = [];

    for (let z = startZ; z <= endZ; z++) {
        for (let x = startX; x <= endX; x++) {
            keys.push(`${x}:${z}`);
        }
    }

    return keys;
}

export function getTerrainObjectDrawRangeSphere(
    object: THREE.Object3D,
    targetCenter: THREE.Vector3,
    targetScale: THREE.Vector3,
): TerrainObjectDrawRangeSphere {
    const precomputed = object.userData.cullBoundingSphere as THREE.Sphere | undefined;
    if (precomputed) {
        targetCenter.copy(precomputed.center);
        return { center: targetCenter, radius: precomputed.radius };
    }

    const instancedMesh = object as THREE.InstancedMesh;
    if (instancedMesh.isInstancedMesh) {
        if (!instancedMesh.boundingSphere) {
            instancedMesh.computeBoundingSphere();
        }
        if (instancedMesh.boundingSphere) {
            targetCenter.copy(instancedMesh.boundingSphere.center).applyMatrix4(object.matrixWorld);
            targetScale.setFromMatrixScale(object.matrixWorld);
            return {
                center: targetCenter,
                radius: instancedMesh.boundingSphere.radius * Math.max(targetScale.x, targetScale.y, targetScale.z),
            };
        }
    }

    const geometry = (object as THREE.Mesh).geometry as THREE.BufferGeometry | undefined;
    if (geometry) {
        if (!geometry.boundingSphere) {
            geometry.computeBoundingSphere();
        }
        if (geometry.boundingSphere) {
            targetCenter.copy(geometry.boundingSphere.center).applyMatrix4(object.matrixWorld);
            targetScale.setFromMatrixScale(object.matrixWorld);
            return {
                center: targetCenter,
                radius: geometry.boundingSphere.radius * Math.max(targetScale.x, targetScale.y, targetScale.z),
            };
        }
    }

    object.getWorldPosition(targetCenter);
    return { center: targetCenter, radius: 0 };
}
