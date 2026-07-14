import * as THREE from 'three';
import { collectTerrainObjectWarmupTextures } from '../src/terrain/TerrainObjectWarmup';

describe('TerrainObjectWarmup', () => {
    it('collects unique object material textures for renderer pre-warmup', () => {
        const texture = new THREE.Texture();
        const root = new THREE.Group();
        root.add(new THREE.Mesh(
            new THREE.BoxGeometry(),
            new THREE.MeshPhongMaterial({ map: texture, alphaMap: texture }),
        ));

        expect(collectTerrainObjectWarmupTextures(root)).toEqual([texture]);
    });
});
