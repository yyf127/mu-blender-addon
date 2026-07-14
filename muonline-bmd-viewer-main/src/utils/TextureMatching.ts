export interface NormalizedTextureName {
    base: string;
    ext: string;
}

const TEXTURE_EXTENSION_PRIORITY = ['ozj', 'ozt', 'tga', 'png', 'jpg', 'jpeg'];

const EQUIVALENT_TEXTURE_EXTENSIONS: Record<string, string[]> = {
    jpg: ['ozj', 'jpeg'],
    jpeg: ['ozj', 'jpg'],
    ozj: ['jpg', 'jpeg', 'png'],
    png: ['ozj', 'ozt'],
    tga: ['ozt', 'png'],
    ozt: ['tga', 'png'],
};

export function normalizeTextureName(path: string): NormalizedTextureName {
    const name = path.split(/[\\/]/).pop()!.toLowerCase();
    const ext = name.includes('.') ? name.split('.').pop()! : '';
    const base = name.replace(/\.[^.]+$/, '');

    return { base, ext };
}

export function areTextureExtensionsCompatible(requiredExt: string, candidateExt: string): boolean {
    const normalizedRequiredExt = requiredExt.toLowerCase();
    const normalizedCandidateExt = candidateExt.toLowerCase();

    return normalizedRequiredExt === normalizedCandidateExt
        || EQUIVALENT_TEXTURE_EXTENSIONS[normalizedRequiredExt]?.includes(normalizedCandidateExt) === true
        || EQUIVALENT_TEXTURE_EXTENSIONS[normalizedCandidateExt]?.includes(normalizedRequiredExt) === true;
}

export function isTextureFileCandidateForRequired(candidateName: string, requiredPath: string): boolean {
    const candidate = normalizeTextureName(candidateName);
    const required = normalizeTextureName(requiredPath);

    return candidate.base === required.base
        && areTextureExtensionsCompatible(required.ext, candidate.ext);
}

export function selectPreferredTextureCandidates<T>(
    candidates: T[],
    requiredTextures: string[],
    getName: (candidate: T) => string,
): T[] {
    const candidatesByBase = new Map<string, T[]>();
    for (const candidate of candidates) {
        const base = normalizeTextureName(getName(candidate)).base;
        const existing = candidatesByBase.get(base) ?? [];
        candidatesByBase.set(base, [...existing, candidate]);
    }

    const selected: T[] = [];
    const selectedBases = new Set<string>();
    for (const requiredTexture of requiredTextures) {
        const required = normalizeTextureName(requiredTexture);
        if (!required.base || selectedBases.has(required.base)) {
            continue;
        }

        const candidatesForBase = candidatesByBase.get(required.base) ?? [];
        const preferred = pickPreferredTextureCandidate(candidatesForBase, requiredTexture, getName);
        if (preferred) {
            selected.push(preferred);
            selectedBases.add(required.base);
        }
    }

    return selected;
}

export function selectPreferredTexturePaths(
    foundTextures: Record<string, string[]>,
    requiredTextures: string[],
): string[] {
    const normalizedFound = new Map<string, string[]>();
    for (const [base, paths] of Object.entries(foundTextures)) {
        normalizedFound.set(base.toLowerCase(), paths);
    }

    const selected: string[] = [];
    const selectedBases = new Set<string>();
    for (const requiredTexture of requiredTextures) {
        const required = normalizeTextureName(requiredTexture);
        if (!required.base || selectedBases.has(required.base)) {
            continue;
        }

        const paths = normalizedFound.get(required.base) ?? [];
        const preferred = pickPreferredTextureCandidate(paths, requiredTexture, path => path);
        if (preferred) {
            selected.push(preferred);
            selectedBases.add(required.base);
        }
    }

    return selected;
}

function pickPreferredTextureCandidate<T>(
    candidates: T[],
    requiredTexture: string,
    getName: (candidate: T) => string,
): T | null {
    let preferred: T | null = null;
    let preferredScore = Number.POSITIVE_INFINITY;
    let preferredName = '';

    for (const candidate of candidates) {
        const name = getName(candidate);
        const score = getTexturePreferenceScore(name, requiredTexture);
        if (score === null) {
            continue;
        }

        const normalizedName = name.toLowerCase();
        if (score < preferredScore || (score === preferredScore && normalizedName.localeCompare(preferredName) < 0)) {
            preferred = candidate;
            preferredScore = score;
            preferredName = normalizedName;
        }
    }

    return preferred;
}

function getTexturePreferenceScore(candidateName: string, requiredPath: string): number | null {
    const candidate = normalizeTextureName(candidateName);
    const required = normalizeTextureName(requiredPath);

    if (candidate.base !== required.base || !areTextureExtensionsCompatible(required.ext, candidate.ext)) {
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
