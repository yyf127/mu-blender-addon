import * as THREE from 'three';

export interface TerrainInstancingEligibility {
    meshCount: number;
    hasSkinnedMeshes: boolean;
    animationCount: number;
}

export function canUseInstancedStaticObjects(eligibility: TerrainInstancingEligibility): boolean {
    return eligibility.meshCount > 0
        && !eligibility.hasSkinnedMeshes
        && eligibility.animationCount === 0;
}

export interface TerrainAnimatedInstancingEligibility {
    meshCount: number;
    hasSkinnedMeshes: boolean;
    instanceCount: number;
    animationCount: number;
    canBakeAnimatedPose: boolean;
}

export function canUseInstancedAnimatedObjects(eligibility: TerrainAnimatedInstancingEligibility): boolean {
    return eligibility.meshCount > 0
        && eligibility.instanceCount > 1
        && eligibility.animationCount > 0
        && eligibility.canBakeAnimatedPose;
}

export function isObjectVisibleInHierarchy(object: THREE.Object3D | null): boolean {
    if (!object) {
        return false;
    }

    let current: THREE.Object3D | null = object;
    while (current) {
        if (!current.visible) {
            return false;
        }
        current = current.parent;
    }

    return true;
}
