import { TERRAIN_SIZE, TWFlags, type TerrainAttributeData } from './formats/ATTReader';

export interface TerrainAttributeFlagDefinition {
    flag: TWFlags;
    name: string;
    hex: string;
}

export interface TerrainAttributeFlagSummary extends TerrainAttributeFlagDefinition {
    count: number;
    active: boolean;
}

export interface TerrainAttributeSummary {
    version: number;
    index: number;
    width: number;
    height: number;
    isExtended: boolean;
    formatLabel: string;
    tileCount: number;
    occupiedTileCount: number;
    flags: TerrainAttributeFlagSummary[];
}

export const TERRAIN_ATTRIBUTE_FLAG_DEFINITIONS: readonly TerrainAttributeFlagDefinition[] = [
    { flag: TWFlags.SafeZone, name: 'SafeZone', hex: '0x0001' },
    { flag: TWFlags.Character, name: 'Character', hex: '0x0002' },
    { flag: TWFlags.NoMove, name: 'NoMove', hex: '0x0004' },
    { flag: TWFlags.NoGround, name: 'NoGround', hex: '0x0008' },
    { flag: TWFlags.Water, name: 'Water', hex: '0x0010' },
    { flag: TWFlags.Action, name: 'Action', hex: '0x0020' },
    { flag: TWFlags.Height, name: 'Height', hex: '0x0040' },
    { flag: TWFlags.CameraUp, name: 'CameraUp', hex: '0x0080' },
    { flag: TWFlags.NoAttackZone, name: 'NoAttackZone', hex: '0x0100' },
    { flag: TWFlags.Att1, name: 'Att1', hex: '0x0200' },
    { flag: TWFlags.Att2, name: 'Att2', hex: '0x0400' },
    { flag: TWFlags.Att3, name: 'Att3', hex: '0x0800' },
    { flag: TWFlags.Att4, name: 'Att4', hex: '0x1000' },
    { flag: TWFlags.Att5, name: 'Att5', hex: '0x2000' },
    { flag: TWFlags.Att6, name: 'Att6', hex: '0x4000' },
    { flag: TWFlags.Att7, name: 'Att7', hex: '0x8000' },
];

export function formatTerrainAttributeFlagHex(flag: TWFlags): string {
    return `0x${flag.toString(16).toUpperCase().padStart(4, '0')}`;
}

export function describeTerrainAttributeFlags(value: number): string[] {
    if (value === TWFlags.None) {
        return [];
    }

    return TERRAIN_ATTRIBUTE_FLAG_DEFINITIONS
        .filter(definition => (value & definition.flag) !== 0)
        .map(definition => definition.name);
}

export function summarizeTerrainAttributeData(data: TerrainAttributeData): TerrainAttributeSummary {
    const flags = TERRAIN_ATTRIBUTE_FLAG_DEFINITIONS.map(definition => ({
        ...definition,
        count: 0,
        active: false,
    }));

    let occupiedTileCount = 0;
    for (const value of data.terrainWall) {
        if (value !== TWFlags.None) {
            occupiedTileCount++;
        }

        for (const flag of flags) {
            if ((value & flag.flag) !== 0) {
                flag.count++;
                flag.active = true;
            }
        }
    }

    return {
        version: data.version,
        index: data.index,
        width: data.width,
        height: data.height,
        isExtended: data.isExtended,
        formatLabel: data.isExtended ? 'Extended (16-bit)' : 'Standard (8-bit)',
        tileCount: TERRAIN_SIZE * TERRAIN_SIZE,
        occupiedTileCount,
        flags,
    };
}
