import * as THREE from 'three';

type MaterialWithTextureSlots = THREE.Material & {
    map?: THREE.Texture | null;
    alphaMap?: THREE.Texture | null;
    aoMap?: THREE.Texture | null;
    bumpMap?: THREE.Texture | null;
    displacementMap?: THREE.Texture | null;
    emissiveMap?: THREE.Texture | null;
    envMap?: THREE.Texture | null;
    lightMap?: THREE.Texture | null;
    metalnessMap?: THREE.Texture | null;
    normalMap?: THREE.Texture | null;
    roughnessMap?: THREE.Texture | null;
    specularMap?: THREE.Texture | null;
};

const TEXTURE_SLOTS = [
    'map',
    'alphaMap',
    'aoMap',
    'bumpMap',
    'displacementMap',
    'emissiveMap',
    'envMap',
    'lightMap',
    'metalnessMap',
    'normalMap',
    'roughnessMap',
    'specularMap',
] as const;

export function collectTerrainObjectWarmupTextures(root: THREE.Object3D): THREE.Texture[] {
    const textures = new Set<THREE.Texture>();

    root.traverse(object => {
        const material = (object as THREE.Mesh).material as THREE.Material | THREE.Material[] | undefined;
        if (!material) {
            return;
        }

        const materials = Array.isArray(material) ? material : [material];
        for (const item of materials) {
            const texturedMaterial = item as MaterialWithTextureSlots;
            for (const slot of TEXTURE_SLOTS) {
                const texture = texturedMaterial[slot];
                if (texture instanceof THREE.Texture) {
                    textures.add(texture);
                }
            }
        }
    });

    return [...textures];
}
