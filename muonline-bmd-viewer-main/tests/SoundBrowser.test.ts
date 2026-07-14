import {
    createSoundPlaybackSource,
    getSoundMimeType,
    type SoundEntry,
} from '../src/sound-browser/SoundBrowser';

describe('SoundBrowser audio sources', () => {
    const originalCreateObjectURL = URL.createObjectURL;

    beforeEach(() => {
        URL.createObjectURL = jest.fn(() => 'blob:audio-source');
    });

    afterEach(() => {
        URL.createObjectURL = originalCreateObjectURL;
        jest.restoreAllMocks();
    });

    it('uses a blob URL for Electron file paths instead of file URLs', async () => {
        const entry: SoundEntry = {
            id: 1,
            name: 'Heaven.wav',
            lowerName: 'heaven.wav',
            path: 'D:\\Mu Online\\Data\\Sound\\Heaven.wav',
            blob: null,
        };

        const source = await createSoundPlaybackSource(entry, async () => ({
            name: 'Heaven.wav',
            data: new Uint8Array([1, 2, 3]).buffer,
        }));

        expect(source).toEqual({ url: 'blob:audio-source', objectUrl: 'blob:audio-source' });
        expect(URL.createObjectURL).toHaveBeenCalledWith(expect.any(Blob));
        expect(source?.url.startsWith('file://')).toBe(false);
    });

    it('assigns stable MIME types for supported sound files', () => {
        expect(getSoundMimeType('alert.wav')).toBe('audio/wav');
        expect(getSoundMimeType('theme.ogg')).toBe('audio/ogg');
        expect(getSoundMimeType('intro.mp3')).toBe('audio/mpeg');
        expect(getSoundMimeType('unknown.bin')).toBe('application/octet-stream');
    });
});
