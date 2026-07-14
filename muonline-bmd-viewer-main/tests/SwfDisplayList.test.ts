import {
  buildSwfDisplayList,
  extractBitmaps,
  parseDefineSprites,
  parseShapeBitmapRefs,
  type SwfTag,
} from '../src/gfx-browser/swf-reader';

function makeTag(type: number, data: number[]): SwfTag {
  return {
    type,
    name: `Tag_${type}`,
    offset: 0,
    length: data.length,
    data: new Uint8Array(data),
  };
}

class BitWriter {
  private bits: number[] = [];

  writeUB(value: number, bitCount: number): void {
    for (let bit = bitCount - 1; bit >= 0; bit--) {
      this.bits.push((value >> bit) & 1);
    }
  }

  writeSB(value: number, bitCount: number): void {
    const encoded = value < 0 ? (1 << bitCount) + value : value;
    this.writeUB(encoded, bitCount);
  }

  toBytes(): number[] {
    const byteCount = Math.ceil(this.bits.length / 8);
    const bytes = new Array(byteCount).fill(0);
    for (let i = 0; i < this.bits.length; i++) {
      bytes[i >> 3] |= this.bits[i] << (7 - (i & 7));
    }
    return bytes;
  }
}

function matrixBytes(translateXTwips: number, translateYTwips: number): number[] {
  const bits = new BitWriter();
  bits.writeUB(0, 1);
  bits.writeUB(0, 1);
  bits.writeUB(12, 5);
  bits.writeSB(translateXTwips, 12);
  bits.writeSB(translateYTwips, 12);
  return bits.toBytes();
}

function rectBytes(xMin: number, xMax: number, yMin: number, yMax: number): number[] {
  const bits = new BitWriter();
  bits.writeUB(12, 5);
  bits.writeSB(xMin, 12);
  bits.writeSB(xMax, 12);
  bits.writeSB(yMin, 12);
  bits.writeSB(yMax, 12);
  return bits.toBytes();
}

function placeObject2(depth: number, charId: number, matrix: number[]): SwfTag {
  return makeTag(26, [
    0x06,
    depth & 0xff,
    depth >> 8,
    charId & 0xff,
    charId >> 8,
    ...matrix,
  ]);
}

function tagRecord(type: number, data: number[]): number[] {
  const header = (type << 6) | data.length;
  return [header & 0xff, header >> 8, ...data];
}

describe('buildSwfDisplayList', () => {
  it('places characters with SWF matrix translation converted to pixels', () => {
    const displayList = buildSwfDisplayList([
      placeObject2(7, 42, matrixBytes(40, 60)),
      makeTag(1, []),
    ]);

    expect(displayList).toEqual([
      expect.objectContaining({
        depth: 7,
        charId: 42,
        matrix: expect.objectContaining({
          translateX: 2,
          translateY: 3,
        }),
      }),
    ]);
  });

  it('removes placed characters by depth before the rendered frame', () => {
    const displayList = buildSwfDisplayList([
      placeObject2(4, 11, matrixBytes(0, 0)),
      makeTag(28, [4, 0]),
      makeTag(1, []),
    ]);

    expect(displayList).toEqual([]);
  });
});

describe('extractBitmaps', () => {
  it('reads CharacterID from DefineBits JPEG tags', async () => {
    const minimalJpegWithSof0 = [
      0xff, 0xd8,
      0xff, 0xc0,
      0x00, 0x11,
      0x08,
      0x00, 0x02,
      0x00, 0x03,
      0x03,
      0x01, 0x11, 0x00,
      0x02, 0x11, 0x00,
      0x03, 0x11, 0x00,
    ];
    const bitmaps = await extractBitmaps([
      makeTag(6, [0x34, 0x12, ...minimalJpegWithSof0]),
    ]);

    expect(bitmaps).toEqual([
      expect.objectContaining({
        charId: 0x1234,
        width: 3,
        height: 2,
      }),
    ]);
  });

  it('extracts DefineBitsJPEG4 images by scanning for JPEG SOI', async () => {
    const minimalJpegWithSof0 = [
      0xff, 0xd8,
      0xff, 0xc0,
      0x00, 0x11,
      0x08,
      0x00, 0x04,
      0x00, 0x05,
      0x03,
      0x01, 0x11, 0x00,
      0x02, 0x11, 0x00,
      0x03, 0x11, 0x00,
    ];
    const bitmaps = await extractBitmaps([
      makeTag(37, [
        0x78, 0x56,
        0, 0, 0, 0,
        0, 0,
        ...minimalJpegWithSof0,
      ]),
    ]);

    expect(bitmaps).toEqual([
      expect.objectContaining({
        charId: 0x5678,
        width: 5,
        height: 4,
      }),
    ]);
  });
});

describe('parseShapeBitmapRefs', () => {
  it('finds bitmap fill styles used by DefineShape tags', () => {
    const refs = parseShapeBitmapRefs([
      makeTag(22, [
        9, 0,
        ...rectBytes(0, 200, 0, 100),
        1,
        0x41,
        42, 0,
        ...matrixBytes(0, 0),
        0,
        0,
      ]),
    ]);

    expect(refs.get(9)).toEqual([
      expect.objectContaining({
        shapeId: 9,
        bitmapId: 42,
        bounds: {
          xMin: 0,
          yMin: 0,
          xMax: 10,
          yMax: 5,
          width: 10,
          height: 5,
        },
      }),
    ]);
  });
});

describe('parseDefineSprites', () => {
  it('extracts nested tags from DefineSprite records', () => {
    const placedShape = placeObject2(1, 9, matrixBytes(20, 40));
    const spriteTags = [
      ...tagRecord(26, Array.from(placedShape.data)),
      ...tagRecord(1, []),
      ...tagRecord(0, []),
    ];
    const sprites = parseDefineSprites([
      makeTag(39, [122, 0, 1, 0, ...spriteTags]),
    ]);

    expect(buildSwfDisplayList(sprites.get(122)?.tags ?? [])).toEqual([
      expect.objectContaining({
        depth: 1,
        charId: 9,
        matrix: expect.objectContaining({
          translateX: 1,
          translateY: 2,
        }),
      }),
    ]);
  });
});
