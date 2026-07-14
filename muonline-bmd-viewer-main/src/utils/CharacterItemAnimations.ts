import * as THREE from 'three';

export interface CharacterItemAnimationPlayback {
    root: THREE.Object3D;
    mixer: THREE.AnimationMixer;
    action: THREE.AnimationAction;
}

export function startCharacterItemAnimation(
    root: THREE.Object3D,
    clips: THREE.AnimationClip[],
    speed: number,
): CharacterItemAnimationPlayback | null {
    const clip = clips.find(candidate => candidate.tracks.length > 0);
    if (!clip) return null;

    const mixer = new THREE.AnimationMixer(root);
    const action = mixer.clipAction(clip);
    action.setEffectiveTimeScale(speed);
    action.reset().play();

    return { root, mixer, action };
}

export function updateCharacterItemAnimationSpeed(
    playbacks: CharacterItemAnimationPlayback[],
    speed: number,
): void {
    playbacks.forEach(playback => {
        playback.action.setEffectiveTimeScale(speed);
    });
}

export function disposeCharacterItemAnimations(playbacks: CharacterItemAnimationPlayback[]): void {
    playbacks.forEach(playback => {
        playback.mixer.stopAllAction();
        playback.mixer.uncacheRoot(playback.root);
    });
    playbacks.length = 0;
}
