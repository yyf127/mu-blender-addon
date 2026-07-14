import * as THREE from 'three';
import { updateTerrainObjectSelectionBox } from '../src/terrain/TerrainObjectSelectionBounds';

describe('TerrainObjectSelectionBounds', () => {
  it('uses the selected object bounds when a concrete object exists', () => {
    const mesh = new THREE.Mesh(new THREE.BoxGeometry(2, 4, 6), new THREE.MeshBasicMaterial());
    mesh.position.set(10, 20, 30);
    const box = new THREE.Box3();

    const updated = updateTerrainObjectSelectionBox({
      object3D: mesh,
      instancedMesh: null,
      instanceId: null,
      approximateRadius: 99,
      selection: { position: { x: 0, y: 0, z: 0 } },
    }, box);

    expect(updated).toBe(true);
    expect(box.min.toArray()).toEqual([9, 18, 27]);
    expect(box.max.toArray()).toEqual([11, 22, 33]);
  });

  it('uses only the selected instanced mesh matrix for instanced objects', () => {
    const geometry = new THREE.BoxGeometry(2, 2, 2);
    const instancedMesh = new THREE.InstancedMesh(geometry, new THREE.MeshBasicMaterial(), 2);
    instancedMesh.setMatrixAt(0, new THREE.Matrix4().makeTranslation(100, 0, 0));
    instancedMesh.setMatrixAt(1, new THREE.Matrix4().makeTranslation(10, 20, 30));
    const box = new THREE.Box3();

    const updated = updateTerrainObjectSelectionBox({
      object3D: null,
      instancedMesh,
      instanceId: 1,
      approximateRadius: 99,
      selection: { position: { x: 0, y: 0, z: 0 } },
    }, box);

    expect(updated).toBe(true);
    expect(box.min.toArray()).toEqual([9, 19, 29]);
    expect(box.max.toArray()).toEqual([11, 21, 31]);
  });

  it('falls back to an approximate box from the selection position', () => {
    const box = new THREE.Box3();

    const updated = updateTerrainObjectSelectionBox({
      object3D: null,
      instancedMesh: null,
      instanceId: null,
      approximateRadius: 5,
      selection: { position: { x: 10, y: 20, z: 30 } },
    }, box);

    expect(updated).toBe(true);
    expect(box.min.toArray()).toEqual([5, 15, 25]);
    expect(box.max.toArray()).toEqual([15, 25, 35]);
  });
});
