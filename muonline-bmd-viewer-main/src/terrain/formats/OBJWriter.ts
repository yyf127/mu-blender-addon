// src/terrain/formats/OBJWriter.ts
import { encryptFileCryptor } from '../../crypto/file-cryptor';
import type { OBJData } from './OBJReader';

const OBJ_RECORD_SIZES: Record<number, number> = {
    0: 30,
    1: 32,
    2: 33,
    3: 45,
    4: 46,
    5: 54,
};

export function writeOBJ(data: OBJData): Uint8Array {
    const objSize = OBJ_RECORD_SIZES[data.version];
    if (objSize === undefined) {
        throw new Error(`OBJ: unsupported version ${data.version}`);
    }
    if (data.objects.length > 0x7fff) {
        throw new Error(`OBJ: too many objects (${data.objects.length})`);
    }

    const plain = new Uint8Array(4 + data.objects.length * objSize);
    const view = new DataView(plain.buffer);
    plain[0] = data.version & 0xff;
    plain[1] = data.mapNumber & 0xff;
    view.setInt16(2, data.objects.length, true);

    let offset = 4;
    for (const object of data.objects) {
        const recordStart = offset;
        view.setInt16(offset, object.type, true); offset += 2;
        view.setFloat32(offset, object.position.x, true); offset += 4;
        view.setFloat32(offset, object.position.y, true); offset += 4;
        view.setFloat32(offset, object.position.z, true); offset += 4;
        view.setFloat32(offset, object.angle.x, true); offset += 4;
        view.setFloat32(offset, object.angle.y, true); offset += 4;
        view.setFloat32(offset, object.angle.z, true); offset += 4;
        view.setFloat32(offset, object.scale, true); offset += 4;

        const extraLength = objSize - 30;
        if (extraLength > 0 && object.extra) {
            plain.set(object.extra.slice(0, extraLength), offset);
        }
        offset = recordStart + objSize;
    }

    return encryptFileCryptor(plain);
}
