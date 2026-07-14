import * as THREE from 'three';

const tempPosition = new THREE.Vector3();
const tempNormal = new THREE.Vector3();
const tempMatrix = new THREE.Matrix4();
const objectToRootMatrix = new THREE.Matrix4();
const rootWorldInverseMatrix = new THREE.Matrix4();
const normalMatrix = new THREE.Matrix3();
const skinMatrix = new THREE.Matrix4();
const boneMatrix = new THREE.Matrix4();

function addScaledMatrix(target: THREE.Matrix4, source: THREE.Matrix4, scale: number): void {
    const targetElements = target.elements;
    const sourceElements = source.elements;

    for (let i = 0; i < 16; i++) {
        targetElements[i] += sourceElements[i] * scale;
    }
}

function applySkinnedNormalTransform(
    skinnedMesh: THREE.SkinnedMesh,
    vertexIndex: number,
    normal: THREE.Vector3,
): void {
    const skinIndex = skinnedMesh.geometry.getAttribute('skinIndex');
    const skinWeight = skinnedMesh.geometry.getAttribute('skinWeight');

    if (!skinIndex || !skinWeight) {
        return;
    }

    const boneMatrices = skinnedMesh.skeleton.boneMatrices;
    if (!boneMatrices) {
        return;
    }

    skinMatrix.elements.fill(0);

    for (let i = 0; i < 4; i++) {
        const weight = skinWeight.getComponent(vertexIndex, i);
        if (weight === 0) continue;

        const boneIndex = skinIndex.getComponent(vertexIndex, i);
        boneMatrix.fromArray(boneMatrices, boneIndex * 16);
        addScaledMatrix(skinMatrix, boneMatrix, weight);
    }

    tempMatrix
        .multiplyMatrices(skinnedMesh.bindMatrixInverse, skinMatrix)
        .multiply(skinnedMesh.bindMatrix);
    normal.applyMatrix4(tempMatrix).normalize();
}

function copyRootTransform(source: THREE.Group, target: THREE.Group): void {
    target.name = source.name;
    target.position.copy(source.position);
    target.quaternion.copy(source.quaternion);
    target.scale.copy(source.scale);
    target.matrixAutoUpdate = source.matrixAutoUpdate;

    if (!source.matrixAutoUpdate) {
        target.matrix.copy(source.matrix);
    }
}

export function updateBakedMeshGeometryToRootSpace(
    mesh: THREE.Mesh,
    rootWorldInverse: THREE.Matrix4,
    bakedGeometry: THREE.BufferGeometry,
    recomputeBounds = true,
): void {
    const sourceGeometry = mesh.geometry as THREE.BufferGeometry;
    const positionAttribute = sourceGeometry.getAttribute('position');
    const normalAttribute = sourceGeometry.getAttribute('normal');
    let bakedPositionAttribute = bakedGeometry.getAttribute('position') as THREE.BufferAttribute | undefined;
    let bakedNormalAttribute = bakedGeometry.getAttribute('normal') as THREE.BufferAttribute | undefined;
    const skinnedMesh = (mesh as THREE.SkinnedMesh).isSkinnedMesh
        ? mesh as THREE.SkinnedMesh
        : null;

    if (!bakedPositionAttribute || bakedPositionAttribute.count !== positionAttribute.count) {
        bakedPositionAttribute = new THREE.Float32BufferAttribute(positionAttribute.count * 3, 3);
        bakedGeometry.setAttribute('position', bakedPositionAttribute);
    }

    if (normalAttribute && (!bakedNormalAttribute || bakedNormalAttribute.count !== normalAttribute.count)) {
        bakedNormalAttribute = new THREE.Float32BufferAttribute(normalAttribute.count * 3, 3);
        bakedGeometry.setAttribute('normal', bakedNormalAttribute);
    }

    objectToRootMatrix.multiplyMatrices(rootWorldInverse, mesh.matrixWorld);
    normalMatrix.getNormalMatrix(objectToRootMatrix);

    if (skinnedMesh) {
        skinnedMesh.skeleton.update();
    }

    for (let i = 0; i < positionAttribute.count; i++) {
        tempPosition.fromBufferAttribute(positionAttribute, i);

        if (skinnedMesh) {
            skinnedMesh.applyBoneTransform(i, tempPosition);
        }

        tempPosition.applyMatrix4(objectToRootMatrix);
        bakedPositionAttribute.setXYZ(i, tempPosition.x, tempPosition.y, tempPosition.z);

        if (!normalAttribute || !bakedNormalAttribute) continue;

        tempNormal.fromBufferAttribute(normalAttribute, i);

        if (skinnedMesh) {
            applySkinnedNormalTransform(skinnedMesh, i, tempNormal);
        }

        tempNormal.applyMatrix3(normalMatrix).normalize();
        bakedNormalAttribute.setXYZ(i, tempNormal.x, tempNormal.y, tempNormal.z);
    }

    bakedPositionAttribute.needsUpdate = true;
    if (normalAttribute && bakedNormalAttribute) {
        bakedNormalAttribute.needsUpdate = true;
    } else {
        bakedGeometry.computeVertexNormals();
    }

    if (recomputeBounds) {
        bakedGeometry.computeBoundingBox();
        bakedGeometry.computeBoundingSphere();
    }
}

export function bakeMeshGeometryToRootSpace(mesh: THREE.Mesh, rootWorldInverse: THREE.Matrix4): THREE.BufferGeometry {
    const sourceGeometry = mesh.geometry as THREE.BufferGeometry;
    const bakedGeometry = sourceGeometry.clone();

    bakedGeometry.deleteAttribute('skinIndex');
    bakedGeometry.deleteAttribute('skinWeight');
    updateBakedMeshGeometryToRootSpace(mesh, rootWorldInverse, bakedGeometry);

    return bakedGeometry;
}

export function bakeSkinnedModelForExport(source: THREE.Group): THREE.Group {
    source.updateMatrixWorld(true);
    rootWorldInverseMatrix.copy(source.matrixWorld).invert();

    const bakedRoot = new THREE.Group();
    copyRootTransform(source, bakedRoot);

    source.traverse(object => {
        const mesh = object as THREE.Mesh;
        if (!mesh.isMesh) return;
        if (!mesh.visible) return;

        const bakedMesh = new THREE.Mesh(
            bakeMeshGeometryToRootSpace(mesh, rootWorldInverseMatrix),
            mesh.material,
        );
        bakedMesh.name = mesh.name;
        bakedMesh.userData = { ...mesh.userData };
        bakedRoot.add(bakedMesh);
    });

    return bakedRoot;
}
