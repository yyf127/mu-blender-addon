export interface MinimapPoint {
  x: number;
  y: number;
}

export interface WorldPoint {
  x: number;
  z: number;
}

export interface MinimapRaster {
  width: number;
  height: number;
  data: Uint8ClampedArray;
}

export function createWorldObjectId(worldNumber: number, type: number, position: WorldPoint): string {
  return [
    worldNumber,
    type,
    position.x.toFixed(2),
    position.z.toFixed(2),
  ].join(':');
}

export function worldToMinimapPoint(
  worldX: number,
  worldZ: number,
  worldSize: number,
  width: number,
  height: number,
): MinimapPoint {
  const x = clamp(worldX / worldSize, 0, 1);
  const z = clamp(worldZ / worldSize, 0, 1);
  return {
    x: x * width,
    y: (1 - z) * height,
  };
}

export function minimapPointToWorld(
  pointX: number,
  pointY: number,
  width: number,
  height: number,
  worldSize: number,
): WorldPoint {
  const normalizedX = clamp(pointX / width, 0, 1);
  const normalizedY = clamp(pointY / height, 0, 1);
  return {
    x: normalizedX * worldSize,
    z: (1 - normalizedY) * worldSize,
  };
}

export function buildHeightMinimapRaster(
  positions: ArrayLike<number>,
  colors: ArrayLike<number> | null,
  vertexGridSize: number,
): MinimapRaster {
  const width = vertexGridSize;
  const height = vertexGridSize;
  const data = new Uint8ClampedArray(width * height * 4);

  let minHeight = Number.POSITIVE_INFINITY;
  let maxHeight = Number.NEGATIVE_INFINITY;
  for (let i = 1; i < positions.length; i += 3) {
    const heightValue = positions[i];
    minHeight = Math.min(minHeight, heightValue);
    maxHeight = Math.max(maxHeight, heightValue);
  }

  const heightRange = Math.max(1, maxHeight - minHeight);

  for (let vy = 0; vy < vertexGridSize; vy++) {
    for (let vx = 0; vx < vertexGridSize; vx++) {
      const vertexIndex = vy * vertexGridSize + vx;
      const heightValue = positions[vertexIndex * 3 + 1];
      const normalizedHeight = clamp((heightValue - minHeight) / heightRange, 0, 1);
      const light = colors
        ? clamp(((colors[vertexIndex * 3] + colors[vertexIndex * 3 + 1] + colors[vertexIndex * 3 + 2]) / 3), 0, 1)
        : 1;

      const shade = Math.round(35 + normalizedHeight * 120 + light * 60);
      const pixelIndex = ((height - 1 - vy) * width + vx) * 4;
      data[pixelIndex] = Math.min(255, shade * 0.62);
      data[pixelIndex + 1] = Math.min(255, shade * 0.82);
      data[pixelIndex + 2] = Math.min(255, shade);
      data[pixelIndex + 3] = 255;
    }
  }

  return { width, height, data };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}
