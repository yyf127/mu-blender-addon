import * as THREE from 'three';
import { startCharacterItemAnimation, updateCharacterItemAnimationSpeed } from '../src/utils/CharacterItemAnimations';

describe('CharacterItemAnimations', () => {
    it('starts a playable item animation on the item root', () => {
        const root = new THREE.Group();
        const bone = new THREE.Bone();
        bone.name = 'WingBone';
        root.add(bone);

        const clip = new THREE.AnimationClip('flap', 1, [
            new THREE.VectorKeyframeTrack('WingBone.position', [0, 1], [0, 0, 0, 10, 0, 0]),
        ]);

        const playback = startCharacterItemAnimation(root, [clip], 0.5);

        expect(playback).not.toBeNull();
        expect(playback?.action.isRunning()).toBe(true);

        playback?.mixer.update(1);
        expect(bone.position.x).toBeCloseTo(5);
    });

    it('ignores items without playable animation clips', () => {
        const root = new THREE.Group();

        expect(startCharacterItemAnimation(root, [], 1)).toBeNull();
        expect(startCharacterItemAnimation(root, [new THREE.AnimationClip('empty', 1, [])], 1)).toBeNull();
    });

    it('updates playback speed for active item animations', () => {
        const root = new THREE.Group();
        const bone = new THREE.Bone();
        bone.name = 'ItemBone';
        root.add(bone);
        const clip = new THREE.AnimationClip('move', 1, [
            new THREE.VectorKeyframeTrack('ItemBone.position', [0, 1], [0, 0, 0, 10, 0, 0]),
        ]);
        const playback = startCharacterItemAnimation(root, [clip], 1);

        updateCharacterItemAnimationSpeed(playback ? [playback] : [], 0.25);
        playback?.mixer.update(1);

        expect(bone.position.x).toBeCloseTo(2.5);
    });
});
