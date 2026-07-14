// src/ozj-browser/OzjBrowser.ts
import { convertOzjToDataUrl } from '../ozj-loader';

// ------------------------------------------------------------------
// Types
// ------------------------------------------------------------------
interface OzjEntry {
    id: number;
    name: string;
    lowerName: string;
    dataUrl: string;
    width: number;
    height: number;
    format: 'OZJ' | 'OZT';
    fileSize: number;
}

let nextId = 0;

function formatBytes(bytes: number): string {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function getImageDimensions(dataUrl: string): Promise<{ width: number; height: number }> {
    return new Promise((resolve, reject) => {
        const img = new Image();
        img.onload = () => resolve({ width: img.naturalWidth, height: img.naturalHeight });
        img.onerror = () => reject(new Error('Image decode failed'));
        img.src = dataUrl;
    });
}

// ------------------------------------------------------------------
// OzjBrowser
// ------------------------------------------------------------------
export class OzjBrowser {
    private entries: OzjEntry[] = [];
    private filteredEntries: OzjEntry[] = [];
    private selectedEntry: OzjEntry | null = null;
    private searchQuery = '';
    private formatFilter: 'all' | 'ozj' | 'ozt' = 'all';
    private isLoading = false;

    // DOM refs — set in init()
    private noDataEl: HTMLElement | null = null;
    private gridWrapEl: HTMLElement | null = null;
    private gridEl: HTMLElement | null = null;
    private previewWrapEl: HTMLElement | null = null;
    private previewImgEl: HTMLImageElement | null = null;
    private previewMetaEl: HTMLElement | null = null;
    private statusEl: HTMLElement | null = null;
    private loadStatusEl: HTMLElement | null = null;
    private statsEl: HTMLElement | null = null;

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    init(): void {
        this.noDataEl      = document.getElementById('ozj-no-data');
        this.gridWrapEl    = document.getElementById('ozj-grid-wrap');
        this.gridEl        = document.getElementById('ozj-grid');
        this.previewWrapEl = document.getElementById('ozj-preview-wrap');
        this.previewImgEl  = document.getElementById('ozj-preview-img') as HTMLImageElement | null;
        this.previewMetaEl = document.getElementById('ozj-preview-meta');
        this.statusEl      = document.getElementById('ozj-status-bar');
        this.loadStatusEl  = document.getElementById('ozj-load-status');
        this.statsEl       = document.getElementById('ozj-stats');

        this.initDropZones();
        this.initSearch();
        this.initFilterButtons();
        this.initNavigation();

        document.getElementById('ozj-clear-btn')?.addEventListener('click', () => this.clearAll());
        document.getElementById('ozj-back-btn')?.addEventListener('click', () => {
            this.selectedEntry = null;
            this.render();
        });

        this.render();
    }

    // ------------------------------------------------------------------
    // File loading
    // ------------------------------------------------------------------

    private initDropZones(): void {
        const fileInput   = document.getElementById('ozj-file-input')   as HTMLInputElement | null;
        const folderInput = document.getElementById('ozj-folder-input') as HTMLInputElement | null;
        const dropZone    = document.getElementById('ozj-drop-zone');
        const folderZone  = document.getElementById('ozj-folder-drop-zone');

        fileInput?.addEventListener('change', () => {
            if (fileInput.files?.length) void this.loadFiles(Array.from(fileInput.files));
            fileInput.value = '';
        });
        folderInput?.addEventListener('change', () => {
            if (folderInput.files?.length) void this.loadFiles(Array.from(folderInput.files));
            folderInput.value = '';
        });

        this.wireDropZone(dropZone,   () => fileInput?.click(),   files => void this.loadFiles(files));
        this.wireDropZone(folderZone, () => folderInput?.click(), files => void this.loadFiles(files));
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

    async loadFiles(files: File[]): Promise<void> {
        const ozFiles = files.filter(f => {
            const l = f.name.toLowerCase();
            return l.endsWith('.ozj') || l.endsWith('.ozt');
        });
        if (ozFiles.length === 0 || this.isLoading) return;
        this.isLoading = true;

        if (this.loadStatusEl) this.loadStatusEl.textContent = `Loading ${ozFiles.length} file(s)…`;
        if (this.statusEl)     this.statusEl.textContent     = 'Loading…';

        let loaded = 0;
        let failed = 0;
        const newEntries: OzjEntry[] = [];

        await Promise.all(ozFiles.map(async file => {
            try {
                const lower  = file.name.toLowerCase();
                const hint: 'ozj' | 'ozt' = lower.endsWith('.ozj') ? 'ozj' : 'ozt';
                const buf    = await file.arrayBuffer();
                const dataUrl = await convertOzjToDataUrl(buf, hint);
                const dims   = await getImageDimensions(dataUrl);
                newEntries.push({
                    id: nextId++,
                    name: file.name,
                    lowerName: lower,
                    dataUrl,
                    width: dims.width,
                    height: dims.height,
                    format: lower.endsWith('.ozj') ? 'OZJ' : 'OZT',
                    fileSize: file.size,
                });
                loaded++;
            } catch {
                failed++;
            }
        }));

        newEntries.sort((a, b) => a.lowerName.localeCompare(b.lowerName));
        this.entries.push(...newEntries);

        const msg = failed > 0
            ? `Loaded ${loaded} file(s), ${failed} failed.`
            : `${this.entries.length} file(s) loaded.`;
        if (this.loadStatusEl) this.loadStatusEl.textContent = msg;

        this.isLoading = false;
        this.applyFilter();
        this.render();
    }

    private clearAll(): void {
        this.entries        = [];
        this.filteredEntries = [];
        this.selectedEntry  = null;
        this.searchQuery    = '';
        const searchInput = document.getElementById('ozj-search') as HTMLInputElement | null;
        if (searchInput) searchInput.value = '';
        // reset format filter buttons
        document.querySelectorAll('.ozj-filter-btn').forEach((b, i) => b.classList.toggle('active', i === 0));
        this.formatFilter = 'all';
        if (this.loadStatusEl) this.loadStatusEl.textContent = 'No files loaded.';
        if (this.statusEl)     this.statusEl.textContent     = 'OZJ Browser';
        if (this.statsEl)      this.statsEl.textContent      = '';
        this.render();
    }

    // ------------------------------------------------------------------
    // Filter / search
    // ------------------------------------------------------------------

    private initSearch(): void {
        const input = document.getElementById('ozj-search') as HTMLInputElement | null;
        input?.addEventListener('input', () => {
            this.searchQuery = input.value.trim().toLowerCase();
            this.applyFilter();
            if (this.selectedEntry && !this.filteredEntries.includes(this.selectedEntry)) {
                this.selectedEntry = null;
            }
            this.render();
        });
    }

    private initFilterButtons(): void {
        document.querySelectorAll<HTMLButtonElement>('.ozj-filter-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.formatFilter = (btn.dataset.format as 'all' | 'ozj' | 'ozt') ?? 'all';
                document.querySelectorAll('.ozj-filter-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.applyFilter();
                if (this.selectedEntry && !this.filteredEntries.includes(this.selectedEntry)) {
                    this.selectedEntry = null;
                }
                this.render();
            });
        });
    }

    private applyFilter(): void {
        this.filteredEntries = this.entries.filter(e => {
            const matchSearch  = !this.searchQuery || e.lowerName.includes(this.searchQuery);
            const matchFormat  = this.formatFilter === 'all'
                || (this.formatFilter === 'ozj' && e.format === 'OZJ')
                || (this.formatFilter === 'ozt' && e.format === 'OZT');
            return matchSearch && matchFormat;
        });
        this.updateStats();
    }

    private updateStats(): void {
        if (this.statsEl) {
            if (this.entries.length === 0) {
                this.statsEl.textContent = '';
                return;
            }
            const ozjCount = this.entries.filter(e => e.format === 'OZJ').length;
            const oztCount = this.entries.filter(e => e.format === 'OZT').length;
            this.statsEl.textContent = `${this.entries.length} total · ${ozjCount} OZJ · ${oztCount} OZT`;
        }
        if (this.statusEl && this.entries.length > 0) {
            this.statusEl.textContent = `${this.filteredEntries.length} / ${this.entries.length} images`;
        }
    }

    // ------------------------------------------------------------------
    // Navigation
    // ------------------------------------------------------------------

    private initNavigation(): void {
        document.getElementById('ozj-prev-btn')?.addEventListener('click', () => this.navigatePrev());
        document.getElementById('ozj-next-btn')?.addEventListener('click', () => this.navigateNext());

        document.addEventListener('keydown', e => {
            const view = document.getElementById('view-ozj');
            if (!view || view.classList.contains('hidden') || this.selectedEntry === null) return;
            if (e.key === 'ArrowLeft')  { e.preventDefault(); this.navigatePrev(); }
            if (e.key === 'ArrowRight') { e.preventDefault(); this.navigateNext(); }
            if (e.key === 'Escape')     { this.selectedEntry = null; this.render(); }
        });
    }

    private navigatePrev(): void {
        if (!this.selectedEntry) return;
        const pos = this.filteredEntries.indexOf(this.selectedEntry);
        if (pos > 0) { this.selectedEntry = this.filteredEntries[pos - 1]; this.renderPreview(); }
    }

    private navigateNext(): void {
        if (!this.selectedEntry) return;
        const pos = this.filteredEntries.indexOf(this.selectedEntry);
        if (pos >= 0 && pos < this.filteredEntries.length - 1) {
            this.selectedEntry = this.filteredEntries[pos + 1];
            this.renderPreview();
        }
    }

    // ------------------------------------------------------------------
    // Rendering
    // ------------------------------------------------------------------

    private render(): void {
        const hasData      = this.entries.length > 0;
        const hasSelection = this.selectedEntry !== null;

        this.noDataEl?.classList.toggle('hidden', hasData);
        this.gridWrapEl?.classList.toggle('hidden', !hasData || hasSelection);
        this.previewWrapEl?.classList.toggle('hidden', !hasSelection);

        if (hasSelection)      this.renderPreview();
        else if (hasData)      this.renderGrid();
    }

    private renderGrid(): void {
        if (!this.gridEl) return;
        this.gridEl.innerHTML = '';

        if (this.filteredEntries.length === 0) {
            const empty = document.createElement('div');
            empty.className   = 'ozj-grid-empty';
            empty.textContent = (this.searchQuery || this.formatFilter !== 'all')
                ? 'No files match the filter.'
                : 'No files loaded.';
            this.gridEl.appendChild(empty);
            return;
        }

        const frag = document.createDocumentFragment();
        for (const entry of this.filteredEntries) {
            const item = document.createElement('button');
            item.type      = 'button';
            item.className = 'ozj-thumb';
            item.title     = `${entry.name}\n${entry.width}×${entry.height} · ${formatBytes(entry.fileSize)}`;

            const img = document.createElement('img');
            img.src       = entry.dataUrl;
            img.alt       = entry.name;
            img.loading   = 'lazy';
            img.className = 'ozj-thumb-img';

            const label = document.createElement('div');
            label.className   = 'ozj-thumb-label';
            label.textContent = entry.name.replace(/\.(ozj|ozt)$/i, '');

            const badge = document.createElement('span');
            badge.className   = `ozj-thumb-badge ozj-badge--${entry.format.toLowerCase()}`;
            badge.textContent = entry.format;

            item.appendChild(img);
            item.appendChild(label);
            item.appendChild(badge);
            item.addEventListener('click', () => { this.selectedEntry = entry; this.render(); });
            frag.appendChild(item);
        }
        this.gridEl.appendChild(frag);
    }

    private renderPreview(): void {
        const entry = this.selectedEntry;
        if (!entry) return;

        if (this.previewImgEl) {
            this.previewImgEl.src = entry.dataUrl;
            this.previewImgEl.alt = entry.name;
        }

        if (this.previewMetaEl) {
            this.previewMetaEl.innerHTML = '';

            const name = document.createElement('span');
            name.className   = 'ozj-preview-name';
            name.textContent = entry.name;

            const badge = document.createElement('span');
            badge.className   = `ozj-preview-badge ozj-badge--${entry.format.toLowerCase()}`;
            badge.textContent = entry.format;

            const dim = document.createElement('span');
            dim.className   = 'ozj-preview-dim';
            dim.textContent = `${entry.width} × ${entry.height} px`;

            const size = document.createElement('span');
            size.className   = 'ozj-preview-size';
            size.textContent = formatBytes(entry.fileSize);

            this.previewMetaEl.append(name, badge, dim, size);
        }

        const pos     = this.filteredEntries.indexOf(entry);
        const prevBtn = document.getElementById('ozj-prev-btn') as HTMLButtonElement | null;
        const nextBtn = document.getElementById('ozj-next-btn') as HTMLButtonElement | null;
        if (prevBtn) prevBtn.disabled = pos <= 0;
        if (nextBtn) nextBtn.disabled = pos < 0 || pos >= this.filteredEntries.length - 1;

        const counter = document.getElementById('ozj-preview-counter');
        if (counter) counter.textContent = pos >= 0 ? `${pos + 1} / ${this.filteredEntries.length}` : '';
    }
}
