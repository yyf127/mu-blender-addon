import * as THREE from 'three';
import {
    ATT_OVERLAY_HEIGHT_OFFSET,
    createTerrainAttOverlayGeometry,
} from '../src/terrain/TerrainAttOverlay';
import { TERRAIN_SIZE, TWFlags, type TerrainAttributeData } from '../src/terrain/formats/ATTReader';

describe('TerrainAttOverlay', () => {
    it('builds ATT overlay vertices slightly above the source terrain heights', () => {
        const sourceGeometry = createSourceTerrainGeometry();
        const attributes = createTerrainAttributes();
        attributes.terrainWall[0] = TWFlags.SafeZone;

        const overlayGeometry = createTerrainAttOverlayGeometry(attributes, sourceGeometry);
        const positions = overlayGeometry.getAttribute('position');

        expect(positions.count).toBe(4);
        expect(positions.getY(0)).toBe(10 + ATT_OVERLAY_HEIGHT_OFFSET);
        expect(positions.getY(1)).toBe(11 + ATT_OVERLAY_HEIGHT_OFFSET);
        expect(positions.getY(2)).toBe(12 + ATT_OVERLAY_HEIGHT_OFFSET);
        expect(positions.getY(3)).toBe(11 + ATT_OVERLAY_HEIGHT_OFFSET);
    });

    it('does not create overlay tiles for empty ATT cells', () => {
        const overlayGeometry = createTerrainAttOverlayGeometry(createTerrainAttributes(), createSourceTerrainGeometry());

        expect(overlayGeometry.getAttribute('position').count).toBe(0);
        expect(overlayGeometry.getIndex()?.count).toBe(0);
    });
});

function createTerrainAttributes(): TerrainAttributeData {
    return {
        version: 1,
        index: 1,
        width: TERRAIN_SIZE,
        height: TERRAIN_SIZE,
        isExtended: false,
        terrainWall: new Uint16Array(TERRAIN_SIZE * TERRAIN_SIZE),
    };
}

function createSourceTerrainGeometry(): THREE.BufferGeometry {
    const vertexGridSize = TERRAIN_SIZE + 1;
    const vertexCount = vertexGridSize * vertexGridSize;
    const positions = new Float32Array(vertexCount * 3);
    const normals = new Float32Array(vertexCount * 3);

    for (let ty = 0; ty < vertexGridSize; ty++) {
        for (let tx = 0; tx < vertexGridSize; tx++) {
            const index = ty * vertexGridSize + tx;
            positions[index * 3] = tx;
            positions[index * 3 + 1] = 10 + tx + ty;
            positions[index * 3 + 2] = ty;

            normals[index * 3 + 1] = 1;
        }
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
    return geometry;
}
