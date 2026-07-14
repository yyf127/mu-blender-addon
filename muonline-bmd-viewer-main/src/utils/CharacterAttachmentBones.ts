import * as THREE from 'three';

export function resolveAttachmentBoneByBmdIndex(
    skeletonBones: THREE.Bone[],
    bmdBones: THREE.Bone[] | null | undefined,
    boneIndex: number,
): THREE.Bone | undefined {
    return bmdBones?.[boneIndex] ?? skeletonBones[boneIndex];
}
