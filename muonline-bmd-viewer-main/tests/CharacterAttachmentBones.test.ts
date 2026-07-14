import * as THREE from 'three';
import { resolveAttachmentBoneByBmdIndex } from '../src/utils/CharacterAttachmentBones';

describe('resolveAttachmentBoneByBmdIndex', () => {
    it('uses BMD-indexed bones when the skeleton has a synthetic armature root', () => {
        const armature = new THREE.Bone();
        armature.name = 'Armature';

        const bmdBones = [
            createBone('Root'),
            createBone('Spine'),
            createBone('LeftHand'),
        ];
        const skeletonBones = [armature, ...bmdBones];

        expect(resolveAttachmentBoneByBmdIndex(skeletonBones, bmdBones, 2)).toBe(bmdBones[2]);
    });

    it('falls back to skeleton bones when BMD-indexed bones are missing', () => {
        const skeletonBones = [
            createBone('Root'),
            createBone('RightHand'),
        ];

        expect(resolveAttachmentBoneByBmdIndex(skeletonBones, null, 1)).toBe(skeletonBones[1]);
    });
});

function createBone(name: string): THREE.Bone {
    const bone = new THREE.Bone();
    bone.name = name;
    return bone;
}
