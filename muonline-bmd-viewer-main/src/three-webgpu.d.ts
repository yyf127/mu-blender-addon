declare module 'three/webgpu' {
  import WebGPURendererClass from 'three/src/renderers/webgpu/WebGPURenderer.js';

  export const WebGPURenderer: typeof WebGPURendererClass;
}

declare module 'three/tsl' {
  export const sRGBTransferEOTF: any;
  export const texture: any;
  export const uv: any;
  export const vec4: any;
  export const vertexColor: any;
}
