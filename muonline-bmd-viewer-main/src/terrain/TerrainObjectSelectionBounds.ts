import * as THREE from 'three';

export interface TerrainObjectBoundsSource {
    object3D: THREE.Object3D | null;
    instancedMesh: THREE.InstancedMesh | null;
    instanceId: number | null;
    approximateRadius: number;
    selection: {
        position: {
            x: number;
            y: number;
            z: number;
        };
    };
}

const tempInstanceMatrix = new THREE.Matrix4();
const tempWorldMatrix = new THREE.Matrix4();
const tempFallbackCenter = new THREE.Vector3();
const tempFallbackSize = new THREE.Vector3();

export function updateTerrainObjectSelectionBox(
    record: TerrainObjectBoundsSource,
    target: THREE.Box3,
): boolean {
    if (record.object3D) {
        record.object3D.updateWorldMatrix(true, true);
        updateSkinnedMeshesBoundingBoxes(record.object3D);
        target.setFromObject(record.object3D);
        if (!target.isEmpty()) {
            return true;
        }
    }

    if (record.instancedMesh && typeof record.instanceId === 'number') {
        const geometry = record.instancedMesh.geometry;
        if (!geometry.boundingBox) {
            geometry.computeBoundingBox();
        }

        if (geometry.boundingBox) {
            record.instancedMesh.updateWorldMatrix(true, false);
            record.instancedMesh.getMatrixAt(record.instanceId, tempInstanceMatrix);
            tempWorldMatrix.multiplyMatrices(record.instancedMesh.matrixWorld, tempInstanceMatrix);
            target.copy(geometry.boundingBox).applyMatrix4(tempWorldMatrix);
            if (!target.isEmpty()) {
                return true;
            }
        }
    }

    const radius = Math.max(1, record.approximateRadius);
    tempFallbackCenter.set(
        record.selection.position.x,
        record.selection.position.y,
        record.selection.position.z,
    );
    tempFallbackSize.setScalar(radius * 2);
    target.setFromCenterAndSize(tempFallbackCenter, tempFallbackSize);
    return true;
}

function updateSkinnedMeshesBoundingBoxes(root: THREE.Object3D) {
    root.traverse(obj => {
        const skinned = obj as THREE.SkinnedMesh;
        if (!skinned.isSkinnedMesh) return;

        const geometry = skinned.geometry as THREE.BufferGeometry;
        const positionAttr = geometry.getAttribute('position');
        if (!positionAttr) return;

        const hasSkinData =
            !!geometry.getAttribute('skinIndex') &&
            !!geometry.getAttribute('skinWeight');

        if (hasSkinData) {
            skinned.computeBoundingBox();
            return;
        }

        if (!skinned.boundingBox) {
            skinned.boundingBox = new THREE.Box3();
        }

        if (geometry.boundingBox === null) {
            geometry.computeBoundingBox();
        }

        if (geometry.boundingBox && skinned.boundingBox) {
            skinned.boundingBox.copy(geometry.boundingBox);
        }
    });
}
