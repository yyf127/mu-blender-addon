jest.mock('../src/crypto/file-cryptor', () => ({
  decryptFileCryptor: jest.fn((buffer: Uint8Array) => buffer),
  xorBuxMask: jest.fn((buffer: Uint8Array) => buffer),
}));

jest.mock('../src/crypto/modulus-cryptor', () => ({
  decryptModulusCryptor: jest.fn((buffer: Uint8Array) => buffer),
}));

import {
  readATT,
  TERRAIN_SIZE,
  TWFlags,
} from '../src/terrain/formats/ATTReader';
import {
  describeTerrainAttributeFlags,
  summarizeTerrainAttributeData,
  TERRAIN_ATTRIBUTE_FLAG_DEFINITIONS,
} from '../src/terrain/TerrainAttributeSummary';

describe('ATT parsing and terrain attribute summaries', () => {
  it('reads standard ATT files and keeps base terrain flags', () => {
    const buffer = createAttBuffer({
      flags: [TWFlags.SafeZone, TWFlags.NoGround, TWFlags.CameraUp],
      extended: false,
      useModulusHeader: false,
    });

    const result = readATT(buffer);

    expect(result.isExtended).toBe(false);
    expect(result.version).toBe(0);
    expect(result.index).toBe(7);
    expect(result.width).toBe(255);
    expect(result.height).toBe(255);
    expect(result.terrainWall).toBeInstanceOf(Uint16Array);
    expect(result.terrainWall[0]).toBe(TWFlags.SafeZone);
    expect(result.terrainWall[1]).toBe(TWFlags.NoGround);
    expect(result.terrainWall[2]).toBe(TWFlags.CameraUp);
  });

  it('reads ATT\\x01 extended files and preserves high-bit flags', () => {
    const flags = [
      TWFlags.NoAttackZone | TWFlags.Att7,
      TWFlags.Att1 | TWFlags.Att4 | TWFlags.Water,
    ];
    const buffer = createAttBuffer({
      flags,
      extended: true,
      useModulusHeader: true,
    });

    const result = readATT(buffer);

    expect(result.isExtended).toBe(true);
    expect(result.terrainWall[0]).toBe(flags[0]);
    expect(result.terrainWall[1]).toBe(flags[1]);
  });

  it('summarizes terrain attribute usage for the sidebar panel', () => {
    const terrainWall = new Uint16Array(TERRAIN_SIZE * TERRAIN_SIZE);
    terrainWall[0] = TWFlags.SafeZone | TWFlags.NoMove;
    terrainWall[1] = TWFlags.NoAttackZone;
    terrainWall[2] = TWFlags.Att7 | TWFlags.Water;

    const summary = summarizeTerrainAttributeData({
      version: 0,
      index: 12,
      width: 255,
      height: 255,
      isExtended: true,
      terrainWall,
    });

    expect(summary.tileCount).toBe(TERRAIN_SIZE * TERRAIN_SIZE);
    expect(summary.occupiedTileCount).toBe(3);
    expect(summary.formatLabel).toBe('Extended (16-bit)');
    expect(summary.flags.find(flag => flag.flag === TWFlags.SafeZone)?.count).toBe(1);
    expect(summary.flags.find(flag => flag.flag === TWFlags.NoMove)?.count).toBe(1);
    expect(summary.flags.find(flag => flag.flag === TWFlags.NoAttackZone)?.count).toBe(1);
    expect(summary.flags.find(flag => flag.flag === TWFlags.Att7)?.count).toBe(1);
    expect(describeTerrainAttributeFlags(TWFlags.SafeZone | TWFlags.NoAttackZone | TWFlags.Att7)).toEqual([
      'SafeZone',
      'NoAttackZone',
      'Att7',
    ]);
    expect(TERRAIN_ATTRIBUTE_FLAG_DEFINITIONS).toHaveLength(16);
  });
});

function createAttBuffer(options: {
  extended: boolean;
  flags: number[];
  useModulusHeader: boolean;
}): ArrayBuffer {
  const bytesPerTile = options.extended ? 2 : 1;
  const payload = new Uint8Array(4 + TERRAIN_SIZE * TERRAIN_SIZE * bytesPerTile);
  payload[0] = 0;
  payload[1] = 7;
  payload[2] = 255;
  payload[3] = 255;

  for (let i = 0; i < options.flags.length; i++) {
    const value = options.flags[i];
    if (options.extended) {
      const offset = 4 + i * 2;
      payload[offset] = value & 0xff;
      payload[offset + 1] = (value >> 8) & 0xff;
    } else {
      payload[4 + i] = value & 0xff;
    }
  }

  if (!options.useModulusHeader) {
    return payload.buffer;
  }

  const withHeader = new Uint8Array(4 + payload.length);
  withHeader[0] = 0x41;
  withHeader[1] = 0x54;
  withHeader[2] = 0x54;
  withHeader[3] = 0x01;
  withHeader.set(payload, 4);
  return withHeader.buffer;
}
