import {
    areTextureExtensionsCompatible,
    normalizeTextureName,
} from '../utils/TextureMatching';

const TEXTURE_FILE_EXTENSION_PATTERN = /\.(jpg|jpeg|png|tga|ozj|ozt)$/i;
const TEXTURE_EXTENSION_PRIORITY = ['ozj', 'ozt', 'tga', 'png', 'jpg', 'jpeg'];

export function selectTerrainObjectTextureCandidates<T>(
    requiredTextureName: string,
    candidates: T[],
    getName: (candidate: T) => string,
): T[] {
    const required = normalizeTextureName(requiredTextureName);
    const requiredBase = normalizeObjectTextureBaseName(required.base);
    if (!requiredBase) {
        return [];
    }

    return candidates
        .map(candidate => ({
            candidate,
            name: getName(candidate),
            score: getTerrainObjectTexturePreferenceScore(requiredTextureName, getName(candidate)),
        }))
        .filter((entry): entry is { candidate: T; name: string; score: number } => entry.score !== null)
        .sort((a, b) => {
            const scoreDiff = a.score - b.score;
            if (scoreDiff !== 0) return scoreDiff;
            return a.name.toLowerCase().localeCompare(b.name.toLowerCase());
        })
        .map(entry => entry.candidate);
}

function getTerrainObjectTexturePreferenceScore(requiredTextureName: string, candidateName: string): number | null {
    if (!TEXTURE_FILE_EXTENSION_PATTERN.test(candidateName)) {
        return null;
    }

    const required = normalizeTextureName(requiredTextureName);
    const candidate = normalizeTextureName(candidateName);
    if (normalizeObjectTextureBaseName(required.base) !== normalizeObjectTextureBaseName(candidate.base)) {
        return null;
    }

    if (
        required.ext &&
        candidate.ext &&
        !areTextureExtensionsCompatible(required.ext, candidate.ext)
    ) {
        return null;
    }

    if (candidate.ext === required.ext) {
        return 0;
    }

    const priorityIndex = TEXTURE_EXTENSION_PRIORITY.indexOf(candidate.ext);
    return priorityIndex === -1
        ? TEXTURE_EXTENSION_PRIORITY.length + 1
        : priorityIndex + 1;
}

function normalizeObjectTextureBaseName(name: string): string {
    return name.toLowerCase().replace(/[^a-z0-9]/g, '');
}
