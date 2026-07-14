jest.mock('three/tsl', () => {
  const node = {
    mul: jest.fn(() => node),
  };
  return {
    sRGBTransferEOTF: jest.fn(() => node),
    texture: jest.fn(() => node),
    uv: jest.fn(() => node),
    vec4: jest.fn(() => node),
    vertexColor: jest.fn(() => node),
  };
});

import * as THREE from 'three';
import {
  createTerrainAtlasGeometryMesh,
  createTerrainMaterial,
  type TerrainAtlas,
} from '../src/terrain/TerrainTexturing';
import { TERRAIN_SIZE, type TerrainAttributeData } from '../src/terrain/formats/ATTReader';
import type { TerrainMappingData } from '../src/terrain/formats/MAPReader';

describe('TerrainTexturing', () => {
  it('uses an unlit material for baked terrain so WebGPU brightness matches shader terrain', () => {
    const atlasTexture = new THREE.Texture();
    const atlas: TerrainAtlas = {
      texture: atlasTexture,
      cols: 1,
      rows: 1,
      count: 1,
      cellSize: 64,
      tileUvScale: 1,
    };
    const mapping: TerrainMappingData = {
      version: 1,
      mapNumber: 1,
      layer1: new Uint8Array(256 * 256),
      layer2: new Uint8Array(256 * 256),
      alpha: new Uint8Array(256 * 256),
    };

    const material = createTerrainMaterial(atlas, mapping, true, 'baked');

    expect(material).toBeInstanceOf(THREE.MeshBasicMaterial);
    expect((material as THREE.MeshBasicMaterial).vertexColors).toBe(true);
  });

  it('builds atlas-uv terrain meshes instead of baking WebGPU terrain into one low-res texture', async () => {
    const sourceGeometry = createSourceTerrainGeometry();
    const attributes = createTerrainAttributes();
    const mapping = createTerrainMapping();
    mapping.layer2[0] = 0;
    mapping.alpha[0] = 128;

    const atlasTexture = new THREE.Texture();
    const atlas: TerrainAtlas = {
      texture: atlasTexture,
      cols: 1,
      rows: 1,
      count: 1,
      cellSize: 64,
      tileUvScale: 1,
    };

    const mesh = await createTerrainAtlasGeometryMesh(sourceGeometry, attributes, atlas, mapping, true);
    const overlay = mesh.children[0] as THREE.Mesh;

    expect(mesh.geometry.getAttribute('uv').count).toBe(TERRAIN_SIZE * TERRAIN_SIZE * 4);
    expect(mesh.userData.minimapGeometry).toBe(sourceGeometry);
    expect(mesh.userData.tileCount).toBe(TERRAIN_SIZE * TERRAIN_SIZE);
    expect((mesh.material as THREE.MeshBasicMaterial).map).toBe(atlasTexture);
    expect((mesh.material as THREE.MeshBasicMaterial).toneMapped).toBe(false);

    expect(overlay).toBeInstanceOf(THREE.Mesh);
    expect(overlay.geometry.getAttribute('color').itemSize).toBe(4);
    expect((overlay.material as THREE.MeshBasicMaterial).transparent).toBe(true);
    expect((overlay.material as THREE.MeshBasicMaterial).map).toBe(atlasTexture);
  });
});

function createTerrainMapping(): TerrainMappingData {
  return {
    version: 1,
    mapNumber: 1,
    layer1: new Uint8Array(TERRAIN_SIZE * TERRAIN_SIZE),
    layer2: new Uint8Array(TERRAIN_SIZE * TERRAIN_SIZE).fill(255),
    alpha: new Uint8Array(TERRAIN_SIZE * TERRAIN_SIZE),
  };
}

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
  const colors = new Float32Array(vertexCount * 3);

  for (let i = 0; i < vertexCount; i++) {
    positions[i * 3] = i % vertexGridSize;
    positions[i * 3 + 1] = 0;
    positions[i * 3 + 2] = Math.floor(i / vertexGridSize);

    normals[i * 3 + 1] = 1;

    colors[i * 3] = 0.5;
    colors[i * 3 + 1] = 0.5;
    colors[i * 3 + 2] = 0.5;
  }

  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geometry.setAttribute('normal', new THREE.BufferAttribute(normals, 3));
  geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  return geometry;
}
