import { selectTerrainObjectTextureCandidates } from '../src/terrain/TerrainObjectTextureSelection';

describe('Terrain object texture selection', () => {
  it('prefers exact MU texture files and ignores same-base non-textures', () => {
    const candidates = [
      { name: 'Object1/Grass04.bmd' },
      { name: 'Object1/Grass04.jpg' },
      { name: 'Object1/Grass04.ozj' },
      { name: 'Object1/Grass04.txt' },
    ];

    const selected = selectTerrainObjectTextureCandidates(
      'Grass04.ozj',
      candidates,
      candidate => candidate.name,
    );

    expect(selected.map(candidate => candidate.name)).toEqual([
      'Object1/Grass04.ozj',
      'Object1/Grass04.jpg',
    ]);
  });

  it('matches texture base names leniently while respecting compatible extensions', () => {
    const candidates = [
      { name: 'Object1/grass_04.png' },
      { name: 'Object1/grass_04.jpg' },
      { name: 'Object1/grass_04.tga' },
    ];

    const selected = selectTerrainObjectTextureCandidates(
      'Grass04.ozt',
      candidates,
      candidate => candidate.name,
    );

    expect(selected.map(candidate => candidate.name)).toEqual([
      'Object1/grass_04.tga',
      'Object1/grass_04.png',
    ]);
  });
});
