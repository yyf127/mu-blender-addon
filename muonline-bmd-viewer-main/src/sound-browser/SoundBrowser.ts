import { isElectron, openDirectoryDialog, readFileFromPath } from '../electron-helper';

export interface SoundEntry {
    id: number;
    name: string;
    lowerName: string;
    path: string | null;
    blob: Blob | null;
}

export interface SoundPlaybackSource {
    url: string;
    objectUrl: string | null;
}

let nextId = 0;

function isSoundFile(name: string): boolean {
    const lower = name.toLowerCase();
    return lower.endsWith('.ogg') || lower.endsWith('.wav') || lower.endsWith('.mp3');
}

export function getSoundMimeType(name: string): string {
    const lower = name.toLowerCase();
    if (lower.endsWith('.ogg')) return 'audio/ogg';
    if (lower.endsWith('.wav')) return 'audio/wav';
    if (lower.endsWith('.mp3')) return 'audio/mpeg';
    return 'application/octet-stream';
}

export async function createSoundPlaybackSource(
    entry: SoundEntry,
    readFile: typeof readFileFromPath = readFileFromPath,
): Promise<SoundPlaybackSource | null> {
    if (entry.blob) {
        const blob = entry.blob.type
            ? entry.blob
            : entry.blob.slice(0, entry.blob.size, getSoundMimeType(entry.name));
        const objectUrl = URL.createObjectURL(blob);
        return { url: objectUrl, objectUrl };
    }

    if (!entry.path) {
        return null;
    }

    const fileData = await readFile(entry.path);
    if (!fileData) {
        return null;
    }

    const blob = new Blob([fileData.data], { type: getSoundMimeType(entry.name) });
    const objectUrl = URL.createObjectURL(blob);
    return { url: objectUrl, objectUrl };
}

export class SoundBrowser {
    private entries: SoundEntry[] = [];
    private filteredEntries: SoundEntry[] = [];
    private selectedEntry: SoundEntry | null = null;
    private searchQuery = '';
    private isLoading = false;
    private currentAudio: HTMLAudioElement | null = null;
    private currentObjectUrl: string | null = null;

    private noDataEl: HTMLElement | null = null;
    private listWrapEl: HTMLElement | null = null;
    private listEl: HTMLElement | null = null;
    private playerWrapEl: HTMLElement | null = null;
    private playBtnEl: HTMLButtonElement | null = null;
    private stopBtnEl: HTMLButtonElement | null = null;
    private volumeSliderEl: HTMLInputElement | null = null;
    private fileNameEl: HTMLElement | null = null;
    private currentTimeEl: HTMLElement | null = null;
    private durationEl: HTMLElement | null = null;
    private progressBarEl: HTMLProgressElement | null = null;
    private statusEl: HTMLElement | null = null;
    private loadStatusEl: HTMLElement | null = null;
    private searchInputEl: HTMLInputElement | null = null;

    init(): void {
        this.noDataEl        = document.getElementById('sound-no-data');
        this.listWrapEl      = document.getElementById('sound-list-wrap');
        this.listEl          = document.getElementById('sound-list');
        this.playerWrapEl    = document.getElementById('sound-player-wrap');
        this.playBtnEl       = document.getElementById('sound-play-btn') as HTMLButtonElement | null;
        this.stopBtnEl       = document.getElementById('sound-stop-btn') as HTMLButtonElement | null;
        this.volumeSliderEl  = document.getElementById('sound-volume-slider') as HTMLInputElement | null;
        this.fileNameEl      = document.getElementById('sound-file-name');
        this.currentTimeEl   = document.getElementById('sound-current-time');
        this.durationEl      = document.getElementById('sound-duration');
        this.progressBarEl   = document.getElementById('sound-progress-bar') as HTMLProgressElement | null;
        this.statusEl        = document.getElementById('sound-status-bar');
        this.loadStatusEl    = document.getElementById('sound-load-status');
        this.searchInputEl   = document.getElementById('sound-search') as HTMLInputElement | null;

        this.initFolderSelector();
        this.initSearch();
        this.initPlayerControls();
        document.getElementById('sound-clear-btn')?.addEventListener('click', () => this.clearAll());

        this.render();
    }

    private initFolderSelector(): void {
        const folderInput = document.getElementById('sound-folder-input') as HTMLInputElement | null;
        const folderZone = document.getElementById('sound-folder-drop-zone');
        const folderBtnEl = document.getElementById('sound-folder-btn');

        if (folderBtnEl) {
            folderBtnEl.addEventListener('click', () => {
                if (isElectron()) {
                    void this.selectFolderElectron();
                } else {
                    folderInput?.click();
                }
            });
        }

        if (folderInput) {
            folderInput.addEventListener('change', () => {
                if (folderInput.files?.length) {
                    void this.loadFilesFromInput(Array.from(folderInput.files));
                    folderInput.value = '';
                }
            });
        }

        this.wireDropZone(folderZone, () => {
            if (isElectron()) {
                void this.selectFolderElectron();
            } else {
                folderInput?.click();
            }
        }, files => void this.loadFilesFromInput(files));
    }

    private wireDropZone(
        zone: HTMLElement | null,
        onClick: () => void,
        onDrop: (files: File[]) => void,
    ): void {
        if (!zone) return;
        zone.addEventListener('click', onClick);
        zone.addEventListener('dragover', e => {
            e.preventDefault();
            zone.classList.add('drop-zone--active');
        });
        zone.addEventListener('dragleave', e => {
            if (!zone.contains(e.relatedTarget as Node)) zone.classList.remove('drop-zone--active');
        });
        zone.addEventListener('drop', e => {
            e.preventDefault();
            zone.classList.remove('drop-zone--active');
            const files = e.dataTransfer?.files ? Array.from(e.dataTransfer.files) : [];
            if (files.length) onDrop(files);
        });
    }

    private async selectFolderElectron(): Promise<void> {
        const folderPath = await openDirectoryDialog();
        if (!folderPath) return;
        if (this.loadStatusEl) this.loadStatusEl.textContent = 'Scanning folder…';

        try {
            if (!window.electronAPI) {
                if (this.loadStatusEl) this.loadStatusEl.textContent = 'Electron API not available.';
                return;
            }

            const soundFiles = await this.readDirectoryElectron(folderPath);
            const entries: SoundEntry[] = [];

            for (const file of soundFiles) {
                if (isSoundFile(file.name)) {
                    entries.push({
                        id: nextId++,
                        name: file.name,
                        lowerName: file.name.toLowerCase(),
                        path: file.path,
                        blob: null,
                    });
                }
            }

            entries.sort((a, b) => a.lowerName.localeCompare(b.lowerName));
            this.entries.push(...entries);

            if (this.loadStatusEl) {
                this.loadStatusEl.textContent = entries.length > 0
                    ? `${entries.length} sound file(s) loaded.`
                    : 'No sound files found in folder.';
            }

            this.isLoading = false;
            this.applyFilter();
            this.render();
        } catch (err) {
            if (this.loadStatusEl) this.loadStatusEl.textContent = 'Failed to read folder.';
        }
    }

    private async readDirectoryElectron(dirPath: string): Promise<Array<{ name: string; path: string }>> {
        if (!window.electronAPI?.readDir) return [];
        return window.electronAPI.readDir(dirPath);
    }

    private async loadFilesFromInput(files: File[]): Promise<void> {
        const soundFiles = files.filter(f => isSoundFile(f.name));
        if (soundFiles.length === 0 || this.isLoading) return;
        this.isLoading = true;

        if (this.loadStatusEl) this.loadStatusEl.textContent = `Loading ${soundFiles.length} file(s)…`;

        const newEntries: SoundEntry[] = [];
        await Promise.all(soundFiles.map(async file => {
            try {
                const blob = file.slice(0, file.size, file.type || getSoundMimeType(file.name));
                newEntries.push({
                    id: nextId++,
                    name: file.name,
                    lowerName: file.name.toLowerCase(),
                    path: null,
                    blob,
                });
            } catch {
                // silently skip failed files
            }
        }));

        newEntries.sort((a, b) => a.lowerName.localeCompare(b.lowerName));
        this.entries.push(...newEntries);

        if (this.loadStatusEl) {
            this.loadStatusEl.textContent = this.entries.length > 0
                ? `${this.entries.length} sound file(s) loaded.`
                : 'No sound files loaded.';
        }

        this.isLoading = false;
        this.applyFilter();
        this.render();
    }

    private initSearch(): void {
        if (!this.searchInputEl) return;
        this.searchInputEl.addEventListener('input', () => {
            this.searchQuery = this.searchInputEl!.value.trim().toLowerCase();
            this.applyFilter();
            if (this.selectedEntry && !this.filteredEntries.includes(this.selectedEntry)) {
                this.selectedEntry = null;
            }
            this.render();
        });
    }

    private applyFilter(): void {
        this.filteredEntries = this.entries.filter(e => {
            const matchSearch = !this.searchQuery || e.lowerName.includes(this.searchQuery);
            return matchSearch;
        });
        this.updateStats();
    }

    private updateStats(): void {
        if (this.statusEl && this.entries.length > 0) {
            this.statusEl.textContent = `${this.filteredEntries.length} / ${this.entries.length} sounds`;
        }
    }

    private initPlayerControls(): void {
        if (this.playBtnEl) {
            this.playBtnEl.addEventListener('click', () => {
                if (this.selectedEntry) {
                    void this.playSound(this.selectedEntry);
                }
            });
        }

        if (this.stopBtnEl) {
            this.stopBtnEl.addEventListener('click', () => this.stopSound());
        }

        if (this.volumeSliderEl) {
            this.volumeSliderEl.addEventListener('input', () => {
                const vol = parseFloat(this.volumeSliderEl!.value);
                if (this.currentAudio) {
                    this.currentAudio.volume = vol;
                }
            });
        }

        if (this.progressBarEl) {
            this.progressBarEl.addEventListener('click', e => {
                if (!this.currentAudio) return;
                const rect = this.progressBarEl!.getBoundingClientRect();
                const percent = (e.clientX - rect.left) / rect.width;
                this.currentAudio.currentTime = percent * this.currentAudio.duration;
            });
        }
    }

    private async playSound(entry: SoundEntry): Promise<void> {
        this.stopSound();

        const source = await createSoundPlaybackSource(entry);
        if (!source) {
            if (this.loadStatusEl) this.loadStatusEl.textContent = 'Failed to read audio file.';
            return;
        }

        this.currentAudio = new Audio();
        this.currentObjectUrl = source.objectUrl;
        this.currentAudio.src = source.url;
        if (this.fileNameEl) this.fileNameEl.textContent = entry.name;
        if (this.loadStatusEl) this.loadStatusEl.textContent = `Ready: ${entry.name}`;

        if (this.volumeSliderEl) {
            this.currentAudio.volume = parseFloat(this.volumeSliderEl.value);
        }

        this.currentAudio.addEventListener('loadedmetadata', () => {
            if (this.durationEl && this.currentAudio) {
                this.durationEl.textContent = this.formatTime(this.currentAudio.duration);
            }
        });

        this.currentAudio.addEventListener('timeupdate', () => {
            if (this.currentTimeEl && this.currentAudio) {
                this.currentTimeEl.textContent = this.formatTime(this.currentAudio.currentTime);
                if (this.progressBarEl) {
                    const duration = this.currentAudio.duration;
                    this.progressBarEl.value = Number.isFinite(duration) && duration > 0
                        ? this.currentAudio.currentTime / duration * 100
                        : 0;
                }
            }
        });

        this.currentAudio.addEventListener('ended', () => {
            this.revokeCurrentObjectUrl();
            this.currentAudio = null;
            if (this.progressBarEl) this.progressBarEl.value = 0;
            if (this.currentTimeEl) this.currentTimeEl.textContent = '0:00';
            if (this.playBtnEl) this.playBtnEl.textContent = 'Play';
        });

        this.currentAudio.addEventListener('error', () => {
            this.stopSound();
            if (this.loadStatusEl) this.loadStatusEl.textContent = 'Failed to load audio.';
        });

        try {
            await this.currentAudio.play();
            if (this.playBtnEl) this.playBtnEl.textContent = 'Pause';
            if (this.loadStatusEl) this.loadStatusEl.textContent = `Playing: ${entry.name}`;
        } catch {
            this.stopSound();
            if (this.loadStatusEl) this.loadStatusEl.textContent = 'Failed to play audio.';
        }
    }

    private stopSound(): void {
        if (this.currentAudio) {
            this.currentAudio.pause();
            this.currentAudio.currentTime = 0;
            this.currentAudio = null;
        }
        this.revokeCurrentObjectUrl();
        if (this.progressBarEl) this.progressBarEl.value = 0;
        if (this.currentTimeEl) this.currentTimeEl.textContent = '0:00';
        if (this.durationEl) this.durationEl.textContent = '0:00';
        if (this.fileNameEl) this.fileNameEl.textContent = this.selectedEntry?.name ?? 'No file selected';
        if (this.playBtnEl) this.playBtnEl.textContent = 'Play';
    }

    private revokeCurrentObjectUrl(): void {
        if (this.currentObjectUrl) {
            URL.revokeObjectURL(this.currentObjectUrl);
            this.currentObjectUrl = null;
        }
    }

    private formatTime(seconds: number): string {
        if (!isFinite(seconds)) return '0:00';
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins}:${secs.toString().padStart(2, '0')}`;
    }

    private clearAll(): void {
        this.stopSound();
        this.entries = [];
        this.filteredEntries = [];
        this.selectedEntry = null;
        this.searchQuery = '';
        if (this.searchInputEl) this.searchInputEl.value = '';
        if (this.loadStatusEl) this.loadStatusEl.textContent = 'No files loaded.';
        if (this.statusEl) this.statusEl.textContent = 'Sound Browser';
        this.render();
    }

    private render(): void {
        const hasData = this.entries.length > 0;

        this.noDataEl?.classList.toggle('hidden', hasData);
        this.listWrapEl?.classList.toggle('hidden', !hasData);
        this.playerWrapEl?.classList.toggle('hidden', !hasData);

        if (hasData) this.renderList();
    }

    private renderList(): void {
        if (!this.listEl) return;
        this.listEl.innerHTML = '';

        if (this.filteredEntries.length === 0) {
            const empty = document.createElement('div');
            empty.className = 'sound-list-empty';
            empty.textContent = this.searchQuery ? 'No files match the filter.' : 'No files loaded.';
            this.listEl.appendChild(empty);
            return;
        }

        const frag = document.createDocumentFragment();
        for (const entry of this.filteredEntries) {
            const item = document.createElement('button');
            item.type = 'button';
            item.className = 'sound-list-item' + (this.selectedEntry === entry ? ' sound-list-item--active' : '');

            const name = document.createElement('span');
            name.className = 'sound-list-item-name';
            name.textContent = entry.name;

            const type = document.createElement('span');
            type.className = 'sound-list-item-type';
            type.textContent = entry.name.split('.').pop()?.toUpperCase() ?? 'AUDIO';

            item.append(name, type);
            item.addEventListener('click', () => {
                this.selectedEntry = entry;
                this.render();
                void this.playSound(entry);
            });
            frag.appendChild(item);
        }
        this.listEl.appendChild(frag);
    }
}
