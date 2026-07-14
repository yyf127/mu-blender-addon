import * as THREE from 'three';
import {
    TerrainObjectCullingIndex,
    getTerrainObjectCullingChunkKeys,
    getTerrainObjectDrawRangeSphere,
} from '../src/terrain/TerrainObjectCulling';

describe('TerrainObjectCulling', () => {
    it('uses InstancedMesh bounds instead of the source geometry bounds', () => {
        const geometry = new THREE.BoxGeometry(2, 2, 2);
        const instancedMesh = new THREE.InstancedMesh(geometry, new THREE.MeshBasicMaterial(), 1);
        instancedMesh.setMatrixAt(0, new THREE.Matrix4().makeTranslation(100, 0, 0));
        instancedMesh.instanceMatrix.needsUpdate = true;
        instancedMesh.computeBoundingSphere();
        instancedMesh.updateMatrixWorld(true);

        const sphere = getTerrainObjectDrawRangeSphere(
            instancedMesh,
            new THREE.Vector3(),
            new THREE.Vector3(),
        );

        expect(sphere.center.x).toBeCloseTo(100);
        expect(sphere.center.y).toBeCloseTo(0);
        expect(sphere.center.z).toBeCloseTo(0);
        expect(sphere.radius).toBeGreaterThan(1);
    });

    it('returns only chunk keys intersecting a culling range', () => {
        expect(getTerrainObjectCullingChunkKeys(1500, 2500, 600, 1000)).toEqual([
            '0:1', '1:1', '2:1',
            '0:2', '1:2', '2:2',
            '0:3', '1:3', '2:3',
        ]);
    });

    it('indexes chunked and fallback objects for distance culling passes', () => {
        const nearChunked = new THREE.Object3D();
        nearChunked.userData.terrainObjectChunkKey = '0:0';
        nearChunked.visible = true;

        const farChunked = new THREE.Object3D();
        farChunked.userData.terrainObjectChunkKey = '5:0';
        farChunked.visible = true;

        const fallback = new THREE.Object3D();
        fallback.visible = true;

        const index = new TerrainObjectCullingIndex();
        index.rebuild([nearChunked, farChunked, fallback]);

        expect(nearChunked.visible).toBe(false);
        expect(farChunked.visible).toBe(false);
        expect(fallback.visible).toBe(false);

        const initialCandidates = index.collectCandidates(
            new THREE.Vector3(10, 0, 10),
            100,
            1000,
        );
        expect(initialCandidates.has(nearChunked)).toBe(true);
        expect(initialCandidates.has(fallback)).toBe(true);
        expect(initialCandidates.has(farChunked)).toBe(false);

        index.replaceVisible(new Set([farChunked]));

        const nextCandidates = index.collectCandidates(
            new THREE.Vector3(10, 0, 10),
            100,
            1000,
        );
        expect(nextCandidates.has(farChunked)).toBe(true);
    });
});
