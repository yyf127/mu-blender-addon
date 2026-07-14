// src/skill-bmd.ts

export type SkillUseTypeLabel = 'None' | 'Master' | 'Brand' | 'MasterLevel' | 'MasterActive';

export interface SkillDefinition {
    id: number;
    name: string;
    requiredLevel: number;
    damage: number;
    manaCost: number;
    abilityCost: number;
    distance: number;
    delay: number;
    requiredEnergy: number;
    requiredLeadership: number;
    masteryType: number;
    skillUseType: number;
    skillUseTypeLabel: SkillUseTypeLabel;
    skillBrand: number;
    killCount: number;
    requireDutyClass: number[];
    requireClass: number[];
    skillRank: number;
    magicIcon: number;
    type: number;
    typeLabel: string;
    requiredStrength: number;
    requiredDexterity: number;
    itemSkill: number;
    isDamage: boolean;
    effect: number;
}

// ------------------------------------------------------------------
// Constants
// ------------------------------------------------------------------
const XOR_KEY = new Uint8Array([0xfc, 0xcf, 0xab]);
const RECORD_SIZE = 88;
const MAX_SKILLS = 1024;
const NAME_LENGTH = 32;

const USE_TYPE_LABELS: SkillUseTypeLabel[] = [
    'None', 'Master', 'Brand', 'MasterLevel', 'MasterActive',
];
const TYPE_LABELS = ['Common Attack', 'Buff', 'De-Buff', 'Friendly'];

// ------------------------------------------------------------------
// Helpers
// ------------------------------------------------------------------
function u16(d: Uint8Array, o: number): number {
    return d[o] | (d[o + 1] << 8);
}
function i32(d: Uint8Array, o: number): number {
    return (d[o] | (d[o + 1] << 8) | (d[o + 2] << 16) | (d[o + 3] << 24)) | 0;
}
function u32(d: Uint8Array, o: number): number {
    return (d[o] | (d[o + 1] << 8) | (d[o + 2] << 16) | (d[o + 3] << 24)) >>> 0;
}

// ------------------------------------------------------------------
// Record parser
// ------------------------------------------------------------------
function parseRecord(dec: Uint8Array, id: number): SkillDefinition | null {
    let end = 0;
    while (end < NAME_LENGTH && dec[end] !== 0) end++;
    const name = new TextDecoder('utf-8', { fatal: false }).decode(dec.subarray(0, end)).trim();
    if (!name) return null;

    let o = NAME_LENGTH;
    const requiredLevel      = u16(dec, o); o += 2;
    const damage             = u16(dec, o); o += 2;
    const manaCost           = u16(dec, o); o += 2;
    const abilityCost        = u16(dec, o); o += 2;
    const distance           = u32(dec, o); o += 4;
    const delay              = i32(dec, o); o += 4;
    const requiredEnergy     = i32(dec, o); o += 4;
    const requiredLeadership = u16(dec, o); o += 2;
    const masteryType        = dec[o++];
    const skillUseTypeRaw    = dec[o++];
    const skillBrand         = u32(dec, o); o += 4;
    const killCount          = dec[o++];
    const requireDutyClass   = Array.from(dec.subarray(o, o + 3)); o += 3;
    const requireClass       = Array.from(dec.subarray(o, o + 7)); o += 7;
    const skillRank          = dec[o++];
    const magicIcon          = u16(dec, o); o += 2;
    const typeRaw            = dec[o++];
    o++; // padding byte
    const requiredStrength   = i32(dec, o); o += 4;
    const requiredDexterity  = i32(dec, o); o += 4;
    const itemSkill          = dec[o++];
    const isDamage           = dec[o++] !== 0;
    const effect             = u16(dec, o);

    return {
        id,
        name,
        requiredLevel,
        damage,
        manaCost,
        abilityCost,
        distance,
        delay,
        requiredEnergy,
        requiredLeadership,
        masteryType,
        skillUseType: skillUseTypeRaw,
        skillUseTypeLabel: USE_TYPE_LABELS[skillUseTypeRaw] ?? 'None',
        skillBrand,
        killCount,
        requireDutyClass,
        requireClass,
        skillRank,
        magicIcon,
        type: typeRaw,
        typeLabel: typeRaw <= 3 ? TYPE_LABELS[typeRaw] : 'None',
        requiredStrength,
        requiredDexterity,
        itemSkill,
        isDamage,
        effect,
    };
}

// ------------------------------------------------------------------
// Public API
// ------------------------------------------------------------------
export function parseSkillBmd(buffer: ArrayBuffer): Map<number, SkillDefinition> {
    const raw = new Uint8Array(buffer);
    const result = new Map<number, SkillDefinition>();
    const dataLen = Math.min(raw.length, RECORD_SIZE * MAX_SKILLS);
    const count = Math.floor(dataLen / RECORD_SIZE);
    const dec = new Uint8Array(RECORD_SIZE);

    for (let i = 0; i < count; i++) {
        const base = i * RECORD_SIZE;
        for (let j = 0; j < RECORD_SIZE; j++) {
            dec[j] = raw[base + j] ^ XOR_KEY[j % 3];
        }
        const skill = parseRecord(dec, i);
        if (skill) result.set(i, skill);
    }

    return result;
}
