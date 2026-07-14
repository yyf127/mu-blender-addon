import { decryptFileCryptor, encryptFileCryptor } from '../src/crypto/file-cryptor';
import { readOBJ } from '../src/terrain/formats/OBJReader';
import { writeOBJ } from '../src/terrain/formats/OBJWriter';

describe('OBJWriter', () => {
  it('round-trips encrypted OBJ data and preserves version-specific extra bytes', () => {
    const plain = new Uint8Array(4 + 33);
    const view = new DataView(plain.buffer);
    plain[0] = 2;
    plain[1] = 7;
    view.setInt16(2, 1, true);

    let offset = 4;
    view.setInt16(offset, 123, true); offset += 2;
    view.setFloat32(offset, 10.5, true); offset += 4;
    view.setFloat32(offset, 20.5, true); offset += 4;
    view.setFloat32(offset, 30.5, true); offset += 4;
    view.setFloat32(offset, 1, true); offset += 4;
    view.setFloat32(offset, 2, true); offset += 4;
    view.setFloat32(offset, 3, true); offset += 4;
    view.setFloat32(offset, 1.25, true); offset += 4;
    plain.set([0xaa, 0xbb, 0xcc], offset);

    const parsed = readOBJ(encryptFileCryptor(plain).buffer);
    const written = writeOBJ({
      version: parsed.version,
      mapNumber: parsed.mapNumber,
      objects: [
        {
          ...parsed.objects[0],
          type: 456,
          position: { x: 11, y: 22, z: 33 },
          angle: { x: 4, y: 5, z: 6 },
          scale: 1.5,
        },
      ],
    });

    const decrypted = decryptFileCryptor(written);
    const writtenView = new DataView(decrypted.buffer, decrypted.byteOffset, decrypted.byteLength);
    expect(decrypted[0]).toBe(2);
    expect(decrypted[1]).toBe(7);
    expect(writtenView.getInt16(2, true)).toBe(1);
    expect(Array.from(decrypted.slice(34, 37))).toEqual([0xaa, 0xbb, 0xcc]);

    const roundTripped = readOBJ(written.buffer);
    expect(roundTripped.objects[0]).toEqual(expect.objectContaining({
      type: 456,
      position: { x: 11, y: 22, z: 33 },
      angle: { x: 4, y: 5, z: 6 },
      scale: 1.5,
      extra: new Uint8Array([0xaa, 0xbb, 0xcc]),
    }));
  });

  it('reads consecutive version 2 records without drifting past record bounds', () => {
    const plain = new Uint8Array(4 + 33 * 2);
    const view = new DataView(plain.buffer);
    plain[0] = 2;
    plain[1] = 7;
    view.setInt16(2, 2, true);

    let offset = 4;
    view.setInt16(offset, 101, true); offset += 2;
    view.setFloat32(offset, 1, true); offset += 4;
    view.setFloat32(offset, 2, true); offset += 4;
    view.setFloat32(offset, 3, true); offset += 4;
    view.setFloat32(offset, 4, true); offset += 4;
    view.setFloat32(offset, 5, true); offset += 4;
    view.setFloat32(offset, 6, true); offset += 4;
    view.setFloat32(offset, 1.1, true); offset += 4;
    plain.set([0x01, 0x02, 0x03], offset); offset += 3;

    view.setInt16(offset, 202, true); offset += 2;
    view.setFloat32(offset, 7, true); offset += 4;
    view.setFloat32(offset, 8, true); offset += 4;
    view.setFloat32(offset, 9, true); offset += 4;
    view.setFloat32(offset, 10, true); offset += 4;
    view.setFloat32(offset, 11, true); offset += 4;
    view.setFloat32(offset, 12, true); offset += 4;
    view.setFloat32(offset, 2.2, true); offset += 4;
    plain.set([0x04, 0x05, 0x06], offset);

    const parsed = readOBJ(encryptFileCryptor(plain).buffer);

    expect(parsed.objects).toHaveLength(2);
    expect(parsed.objects[0]).toEqual(expect.objectContaining({
      type: 101,
      position: { x: 1, y: 2, z: 3 },
      angle: { x: 4, y: 5, z: 6 },
      extra: new Uint8Array([0x01, 0x02, 0x03]),
    }));
    expect(parsed.objects[1]).toEqual(expect.objectContaining({
      type: 202,
      position: { x: 7, y: 8, z: 9 },
      angle: { x: 10, y: 11, z: 12 },
      extra: new Uint8Array([0x04, 0x05, 0x06]),
    }));
  });
});
