import { defineConfig } from 'vite';

const THREE_WEBGPU_MODULES = new RegExp([
  String.raw`node_modules[\\/]three[\\/]`,
  String.raw`(?:`,
  String.raw`(?:webgpu|tsl)(?:\.js)?`,
  String.raw`|build[\\/]three\.(?:webgpu|tsl)\.js`,
  String.raw`|src[\\/](?:renderers[\\/]webgpu|nodes)(?:[\\/]|$)`,
  String.raw`)`,
].join(''));

// Use './' for Electron compatibility, or set VITE_BASE_PATH for GitHub Pages
export default defineConfig({
  base: process.env.VITE_BASE_PATH || './',
  build: {
    chunkSizeWarningLimit: 650,
    rolldownOptions: {
      output: {
        codeSplitting: {
          minSize: 20_000,
          groups: [
            {
              name: 'vendor-three-webgpu',
              test: THREE_WEBGPU_MODULES,
              priority: 4,
              maxSize: 650_000,
            },
            {
              name: 'vendor-three',
              test: /node_modules[\\/]three[\\/]/,
              priority: 3,
              maxSize: 450_000,
            },
            {
              name: 'vendor-gif',
              test: /node_modules[\\/]gif\.js[\\/]/,
              priority: 2,
            },
            {
              name: 'vendor',
              test: /node_modules[\\/]/,
              priority: 1,
              maxSize: 450_000,
            },
          ],
        },
      },
    },
  },
});
