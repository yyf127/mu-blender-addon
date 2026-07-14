export function decodeDdsToRgba(
  width: number,
  height: number,
  format: 'DXT1' | 'DXT3' | 'DXT5',
  data: Uint8Array,
): Uint8Array {
  const bw = Math.ceil(width / 4);
  const bh = Math.ceil(height / 4);
  const blockSize = format === 'DXT1' ? 8 : 16;
  const out = new Uint8Array(width * height * 4);

  let src = 0;
  for (let by = 0; by < bh; by++) {
    for (let bx = 0; bx < bw; bx++) {
      if (src + blockSize > data.length) return out;
      decodeBlock(data, src, format, out, bx * 4, by * 4, width, height);
      src += blockSize;
    }
  }
  return out;
}

function rgb565(v: number): [number, number, number] {
  return [
    ((v >> 11) & 0x1F) * 255 / 31 + 0.5 | 0,
    ((v >> 5) & 0x3F) * 255 / 63 + 0.5 | 0,
    (v & 0x1F) * 255 / 31 + 0.5 | 0,
  ];
}

function decodeBlock(
  data: Uint8Array, off: number, fmt: string,
  out: Uint8Array, bx: number, by: number, w: number, h: number,
): void {
  const colorOff = fmt === 'DXT1' ? off : off + 8;

  const c0v = data[colorOff] | (data[colorOff + 1] << 8);
  const c1v = data[colorOff + 2] | (data[colorOff + 3] << 8);
  const c0 = rgb565(c0v);
  const c1 = rgb565(c1v);

  const colors: [number, number, number][] = [c0, c1, [0, 0, 0], [0, 0, 0]];
  if (c0v > c1v || fmt !== 'DXT1') {
    for (let i = 0; i < 3; i++) {
      colors[2][i] = (2 * c0[i] + c1[i] + 1) / 3 | 0;
      colors[3][i] = (c0[i] + 2 * c1[i] + 1) / 3 | 0;
    }
  } else {
    for (let i = 0; i < 3; i++) colors[2][i] = (c0[i] + c1[i]) >> 1;
  }

  for (let py = 0; py < 4; py++) {
    const y = by + py;
    if (y >= h) continue;
    const bits = data[colorOff + 4 + py];
    for (let px = 0; px < 4; px++) {
      const x = bx + px;
      if (x >= w) continue;
      const ci = (bits >> (px * 2)) & 3;
      const di = (y * w + x) * 4;
      out[di] = colors[ci][0];
      out[di + 1] = colors[ci][1];
      out[di + 2] = colors[ci][2];
      out[di + 3] = 255;
    }
  }

  if (fmt === 'DXT1' && c0v <= c1v) {
    for (let py = 0; py < 4; py++) {
      const y = by + py;
      if (y >= h) continue;
      const bits = data[colorOff + 4 + py];
      for (let px = 0; px < 4; px++) {
        if (((bits >> (px * 2)) & 3) === 3) {
          const x = bx + px;
          if (x < w) out[(y * w + x) * 4 + 3] = 0;
        }
      }
    }
  } else if (fmt === 'DXT3') {
    for (let j = 0; j < 16; j++) {
      const py = j >> 2, px = j & 3;
      const y = by + py, x = bx + px;
      if (y >= h || x >= w) continue;
      const byte = data[off + (j >> 1)];
      const a4 = (j & 1) ? (byte >> 4) & 0xF : byte & 0xF;
      out[(y * w + x) * 4 + 3] = a4 * 17;
    }
  } else if (fmt === 'DXT5') {
    const a0 = data[off], a1 = data[off + 1];
    const alphas = new Uint8Array(8);
    alphas[0] = a0;
    alphas[1] = a1;
    if (a0 > a1) {
      for (let i = 1; i <= 6; i++) alphas[i + 1] = ((7 - i) * a0 + i * a1 + 3) / 7 | 0;
    } else {
      for (let i = 1; i <= 4; i++) alphas[i + 1] = ((5 - i) * a0 + i * a1 + 2) / 5 | 0;
      alphas[6] = 0;
      alphas[7] = 255;
    }

    const lo = data[off + 2] | (data[off + 3] << 8) | (data[off + 4] << 16);
    const hi = data[off + 5] | (data[off + 6] << 8) | (data[off + 7] << 16);

    for (let j = 0; j < 16; j++) {
      const py = j >> 2, px = j & 3;
      const y = by + py, x = bx + px;
      if (y >= h || x >= w) continue;
      const ai = j < 8 ? (lo >> (j * 3)) & 7 : (hi >> ((j - 8) * 3)) & 7;
      out[(y * w + x) * 4 + 3] = alphas[ai];
    }
  }
}
