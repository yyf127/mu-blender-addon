// src/item-bmd.ts

export interface ItemDefinition {
    index: number;
    group: number;
    id: number;
    modelFolder: string;
    modelName: string;
    itemName: string;
    modelPath: string;
    // Geometry
    width: number;
    height: number;
    // Classification
    kindA: number;
    kindB: number;
    type: number;
    twoHands: boolean;
    // Stats
    dropLevel: number;
    slot: number;
    skillIndex: number;
    damageMin: number;
    damageMax: number;
    defenseRate: number;
    defense: number;
    magicResistance: number;
    attackSpeed: number;
    durability: number;
    // Requirements
    reqStr: number;
    reqDex: number;
    reqEne: number;
    reqVit: number;
    reqCmd: number;
    reqLvl: number;
    // Economy
    itemValue: number;
    money: number;
}

const XOR_KEY = new Uint8Array([0xfc, 0xcf, 0xab]);

function xorBuffer(data: Uint8Array): void {
    for (let i = 0; i < data.length; i++) {
        data[i] ^= XOR_KEY[i % XOR_KEY.length];
    }
}

function readFixedString(view: DataView, offset: number, length: number): string {
    if (offset + length > view.byteLength) return '';
    const bytes = new Uint8Array(view.buffer, view.byteOffset + offset, length);
    const zero = bytes.indexOf(0);
    const slice = zero >= 0 ? bytes.subarray(0, zero) : bytes;
    return new TextDecoder('windows-1252', { fatal: false }).decode(slice).trim();
}

function normalizePath(input: string): string {
    return input.replace(/\\/g, '/').replace(/^\/+/, '');
}

export function buildModelPath(folder: string, name: string): string {
    const cleanFolder = normalizePath(folder.trim());
    const cleanName = normalizePath(name.trim());

    if (!cleanName) return '';
    if (!cleanFolder) return cleanName;
    if (cleanName.includes('/')) return cleanName;

    return cleanFolder.endsWith('/')
        ? `${cleanFolder}${cleanName}`
        : `${cleanFolder}/${cleanName}`;
}

export function parseItemBmd(buffer: ArrayBuffer): ItemDefinition[] {
    const view = new DataView(buffer);
    if (view.byteLength < 8) return [];

    const itemCount = view.getInt32(0, true);
    if (itemCount <= 0) return [];

    const bytesPerItem = Math.floor((view.byteLength - 8) / itemCount);
    if (bytesPerItem <= 0) return [];

    const items: ItemDefinition[] = [];
    let offset = 4;

    for (let i = 0; i < itemCount && offset + bytesPerItem <= view.byteLength - 4; i++) {
        const raw = new Uint8Array(buffer, offset, bytesPerItem);
        const copy = new Uint8Array(raw);
        xorBuffer(copy);

        const v = new DataView(copy.buffer, copy.byteOffset, copy.byteLength);

        const index       = v.getInt32(0, true);
        const group       = v.getUint16(4, true);
        const id          = v.getUint16(6, true);

        const modelFolder = readFixedString(v, 8, 260);
        const modelName   = readFixedString(v, 268, 260);
        const itemName    = readFixedString(v, 528, 64);

        const kindA       = copy[592];
        const kindB       = copy[593];
        const type        = copy[594];
        const twoHands    = copy[595] !== 0;
        const dropLevel   = v.getUint16(596, true);
        const slot        = v.getUint16(598, true);
        const skillIndex  = v.getUint16(600, true);
        const width       = copy[602];
        const height      = copy[603];
        const damageMin   = v.getUint16(604, true);
        const damageMax   = v.getUint16(606, true);
        const defenseRate = v.getUint16(608, true);
        const defense     = v.getUint16(610, true);
        const magicResistance = v.getUint16(612, true);
        const attackSpeed = copy[614];
        const durability  = copy[616];

        const reqStr      = bytesPerItem > 630 ? v.getUint16(628, true) : 0;
        const reqDex      = bytesPerItem > 632 ? v.getUint16(630, true) : 0;
        const reqEne      = bytesPerItem > 634 ? v.getUint16(632, true) : 0;
        const reqVit      = bytesPerItem > 636 ? v.getUint16(634, true) : 0;
        const reqCmd      = bytesPerItem > 638 ? v.getUint16(636, true) : 0;
        const reqLvl      = bytesPerItem > 640 ? v.getUint16(638, true) : 0;

        const itemValue   = bytesPerItem > 644 ? v.getInt32(640, true) : 0;
        const money       = bytesPerItem > 648 ? v.getInt32(644, true) : 0;

        const modelPath = buildModelPath(modelFolder, modelName);

        items.push({
            index, group, id,
            modelFolder, modelName, itemName, modelPath,
            width, height,
            kindA, kindB, type, twoHands,
            dropLevel, slot, skillIndex,
            damageMin, damageMax, defenseRate, defense, magicResistance,
            attackSpeed, durability,
            reqStr, reqDex, reqEne, reqVit, reqCmd, reqLvl,
            itemValue, money,
        });

        offset += bytesPerItem;
    }

    return items;
}
