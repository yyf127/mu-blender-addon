import * as THREE from 'three';
import { bakeSkinnedModelForExport } from '../src/utils/SkinnedMeshBaker';

describe('bakeSkinnedModelForExport', () => {
    it('bakes skinned vertex positions into a static mesh for importers that ignore skinning', () => {
        const root = new THREE.Group();
        root.name = 'bmd_model';

        const bone = new THREE.Bone();
        bone.name = 'bone_0';
        root.add(bone);

        const skeleton = new THREE.Skeleton([bone]);
        const geometry = new THREE.BufferGeometry();
        geometry.setAttribute('position', new THREE.Float32BufferAttribute([0, 1, 0], 3));
        geometry.setAttribute('normal', new THREE.Float32BufferAttribute([0, 1, 0], 3));
        geometry.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0], 2));
        geometry.setAttribute('skinIndex', new THREE.Uint16BufferAttribute([0, 0, 0, 0], 4));
        geometry.setAttribute('skinWeight', new THREE.Float32BufferAttribute([1, 0, 0, 0], 4));

        const skinnedMesh = new THREE.SkinnedMesh(geometry, new THREE.MeshBasicMaterial());
        skinnedMesh.name = 'skinned_part';
        skinnedMesh.bind(skeleton);
        root.add(skinnedMesh);

        bone.position.set(0, 10, 0);

        const baked = bakeSkinnedModelForExport(root);
        const bakedMesh = baked.children[0] as THREE.Mesh;
        const bakedGeometry = bakedMesh.geometry as THREE.BufferGeometry;
        const bakedPosition = bakedGeometry.getAttribute('position');

        expect(baked.children).toHaveLength(1);
        expect(bakedMesh.name).toBe('skinned_part');
        expect(bakedGeometry.getAttribute('skinIndex')).toBeUndefined();
        expect(bakedGeometry.getAttribute('skinWeight')).toBeUndefined();
        expect(bakedPosition.getX(0)).toBeCloseTo(0);
        expect(bakedPosition.getY(0)).toBeCloseTo(11);
        expect(bakedPosition.getZ(0)).toBeCloseTo(0);
    });

    it('preserves the source root transform while storing baked vertices in root-local space', () => {
        const root = new THREE.Group();
        root.rotation.x = -Math.PI / 2;

        const mesh = new THREE.Mesh(
            new THREE.BufferGeometry().setAttribute(
                'position',
                new THREE.Float32BufferAttribute([0, 2, 0], 3),
            ),
            new THREE.MeshBasicMaterial(),
        );
        mesh.position.set(0, 3, 0);
        root.add(mesh);

        const baked = bakeSkinnedModelForExport(root);
        const bakedMesh = baked.children[0] as THREE.Mesh;
        const bakedPosition = bakedMesh.geometry.getAttribute('position');

        expect(baked.rotation.x).toBeCloseTo(root.rotation.x);
        expect(bakedMesh.position.toArray()).toEqual([0, 0, 0]);
        expect(bakedPosition.getX(0)).toBeCloseTo(0);
        expect(bakedPosition.getY(0)).toBeCloseTo(5);
        expect(bakedPosition.getZ(0)).toBeCloseTo(0);
    });
});
