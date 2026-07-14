import {
  areTextureExtensionsCompatible,
  isTextureFileCandidateForRequired,
  selectPreferredTextureCandidates,
  selectPreferredTexturePaths,
} from '../src/utils/TextureMatching';

describe('TextureMatching', () => {
  it('matches equivalent MU texture extensions by base name', () => {
    expect(areTextureExtensionsCompatible('jpg', 'ozj')).toBe(true);
    expect(areTextureExtensionsCompatible('ozt', 'tga')).toBe(true);
    expect(isTextureFileCandidateForRequired('PlayerBody.ozj', 'Data\\Player\\PlayerBody.jpg')).toBe(true);
    expect(isTextureFileCandidateForRequired('PlayerHead.ozj', 'Data\\Player\\PlayerBody.jpg')).toBe(false);
  });

  it('selects only one best matching texture per required base', () => {
    const files = [
      { name: 'unrelated.ozj' },
      { name: 'armor.ozj' },
      { name: 'armor.jpg' },
      { name: 'weapon.png' },
      { name: 'weapon.tga' },
    ];

    const selected = selectPreferredTextureCandidates(
      files,
      ['Armor.jpg', 'Weapon.ozt'],
      file => file.name,
    );

    expect(selected.map(file => file.name)).toEqual(['armor.jpg', 'weapon.tga']);
  });

  it('selects preferred paths from Electron search results without loading every variant', () => {
    const selected = selectPreferredTexturePaths({
      armor: [
        'D:\\Data\\Object1\\armor.ozj',
        'D:\\Data\\Object1\\armor.jpg',
      ],
      weapon: [
        'D:\\Data\\Object1\\weapon.png',
        'D:\\Data\\Object1\\weapon.ozt',
      ],
      unrelated: [
        'D:\\Data\\Object1\\unrelated.ozj',
      ],
    }, ['Data\\Object1\\Armor.jpg', 'Data\\Object1\\Weapon.ozt']);

    expect(selected).toEqual([
      'D:\\Data\\Object1\\armor.jpg',
      'D:\\Data\\Object1\\weapon.ozt',
    ]);
  });
});
