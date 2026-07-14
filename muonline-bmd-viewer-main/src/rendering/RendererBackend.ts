import * as THREE from 'three';

export type RendererBackendActive = 'webgpu' | 'webgl';
export type RendererBackendPreference = 'auto' | RendererBackendActive;

export type WebGpuRendererOptions = {
    antialias?: boolean;
    alpha?: boolean;
};

export type WebGpuRenderer = {
    backend: {
        isWebGPUBackend?: boolean;
        getMaxAnisotropy?: () => number;
    };
    debug?: {
        checkShaderErrors?: boolean;
    };
    domElement: HTMLCanvasElement;
    outputColorSpace: THREE.ColorSpace;
    toneMapping: THREE.ToneMapping;
    toneMappingExposure: number;
    shadowMap: {
        enabled: boolean;
        type: THREE.ShadowMapType;
    };
    init(): Promise<unknown>;
    dispose(): void;
    render(scene: THREE.Object3D, camera: THREE.Camera): void;
    setPixelRatio(value: number): void;
    setSize(width: number, height: number, updateStyle?: boolean): void;
    initTexture?: (texture: THREE.Texture) => void;
    compile?: (scene: THREE.Object3D, camera: THREE.Camera, targetScene?: THREE.Scene | null) => unknown;
    compileAsync?: (scene: THREE.Object3D, camera: THREE.Camera, targetScene?: THREE.Scene | null) => Promise<unknown>;
};

export type SupportedRenderer = THREE.WebGLRenderer | WebGpuRenderer;

export function isWebGLRenderer(renderer: SupportedRenderer): renderer is THREE.WebGLRenderer {
    return renderer instanceof THREE.WebGLRenderer;
}

export function getActiveRendererBackend(renderer: SupportedRenderer): RendererBackendActive {
    if (isWebGLRenderer(renderer)) {
        return 'webgl';
    }

    return renderer.backend.isWebGPUBackend ? 'webgpu' : 'webgl';
}

export async function createPreferredRenderer(
    preference: RendererBackendPreference,
    createWebGLRenderer: () => THREE.WebGLRenderer,
    webgpuOptions: WebGpuRendererOptions,
): Promise<SupportedRenderer> {
    if (preference === 'webgl') {
        return createWebGLRenderer();
    }

    const { WebGPURenderer } = await import('three/webgpu');
    return new WebGPURenderer(webgpuOptions) as WebGpuRenderer;
}
