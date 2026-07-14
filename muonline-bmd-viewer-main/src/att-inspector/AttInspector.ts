// src/att-inspector/AttInspector.ts
import { TERRAIN_SIZE, TWFlags, type TerrainAttributeData, readATT } from '../terrain/formats/ATTReader';
import {
    TERRAIN_ATTRIBUTE_FLAG_DEFINITIONS,
    describeTerrainAttributeFlags,
    formatTerrainAttributeFlagHex,
    summarizeTerrainAttributeData,
    type TerrainAttributeFlagSummary,
    type TerrainAttributeSummary,
} from '../terrain/TerrainAttributeSummary';

// ------------------------------------------------------------------
// Flag color palette  [r, g, b]
// ------------------------------------------------------------------
const FLAG_COLOR_MAP: ReadonlyMap<TWFlags, readonly [number, number, number]> = new Map([
    [TWFlags.SafeZone,     [68,  136, 255]],
    [TWFlags.Character,    [245, 158,  11]],
    [TWFlags.NoMove,       [248, 113, 113]],
    [TWFlags.NoGround,     [167, 139, 250]],
    [TWFlags.Water,        [ 34, 211, 238]],
    [TWFlags.Action,       [ 52, 211, 153]],
    [TWFlags.Height,       [251, 146,  60]],
    [TWFlags.CameraUp,     [232, 121, 249]],
    [TWFlags.NoAttackZone, [244, 114, 182]],
    [TWFlags.Att1,         [250, 204,  21]],
    [TWFlags.Att2,         [163, 230,  53]],
    [TWFlags.Att3,         [ 45, 212, 191]],
    [TWFlags.Att4,         [ 96, 165, 250]],
    [TWFlags.Att5,         [251, 113, 133]],
    [TWFlags.Att6,         [156, 163, 175]],
    [TWFlags.Att7,         [209, 213, 219]],
]);

export function getAttFlagColor(flag: TWFlags): readonly [number, number, number] {
    return FLAG_COLOR_MAP.get(flag) ?? [128, 128, 128];
}

export function getAttFlagColorCss(flag: TWFlags): string {
    const [r, g, b] = getAttFlagColor(flag);
    return `rgb(${r},${g},${b})`;
}

// ------------------------------------------------------------------
// AttInspector
// ------------------------------------------------------------------
export class AttInspector {
    public onTileClicked?: (tileX: number, tileY: number, value: number) => void;

    private attData: TerrainAttributeData | null = null;
    private summary: TerrainAttributeSummary | null = null;
    private worldNumber: number | null = null;
    private loadedFileName: string | null = null;

    /** Flags hidden by the user (clicked off in legend). */
    private readonly hiddenFlags = new Set<TWFlags>();

    // Off-screen drawing surface (256×256 native resolution)
    private readonly offscreenCanvas = document.createElement('canvas');
    private readonly offscreenCtx: CanvasRenderingContext2D;
    private readonly baseImageData: ImageData;
    private baseDirty = true;

    // Overlay canvas (hover highlight + crosshair, same native res)
    private readonly overlayCanvas = document.createElement('canvas');
    private readonly overlayCtx: CanvasRenderingContext2D;

    // DOM refs
    private mapCanvas: HTMLCanvasElement | null = null;
    private tooltipEl: HTMLElement | null = null;
    private statusEl: HTMLElement | null = null;
    private legendEl: HTMLElement | null = null;
    private metaEl: HTMLElement | null = null;
    private noDataEl: HTMLElement | null = null;
    private mapWrapEl: HTMLElement | null = null;

    private lastHoverTile: { x: number; y: number } | null = null;

    constructor() {
        this.offscreenCanvas.width = TERRAIN_SIZE;
        this.offscreenCanvas.height = TERRAIN_SIZE;
        this.offscreenCtx = this.offscreenCanvas.getContext('2d')!;
        this.baseImageData = this.offscreenCtx.createImageData(TERRAIN_SIZE, TERRAIN_SIZE);

        this.overlayCanvas.width = TERRAIN_SIZE;
        this.overlayCanvas.height = TERRAIN_SIZE;
        this.overlayCtx = this.overlayCanvas.getContext('2d')!;
    }

    // ------------------------------------------------------------------
    // Public API
    // ------------------------------------------------------------------

    init(): void {
        this.mapCanvas  = document.getElementById('att-map-canvas')  as HTMLCanvasElement | null;
        this.tooltipEl  = document.getElementById('att-tooltip');
        this.statusEl   = document.getElementById('att-inspector-status');
        this.legendEl   = document.getElementById('att-legend');
        this.metaEl     = document.getElementById('att-meta-grid');
        this.noDataEl   = document.getElementById('att-no-data');
        this.mapWrapEl  = document.getElementById('att-map-wrap');

        if (this.mapCanvas) {
            this.mapCanvas.addEventListener('mousemove',  e => this.onMouseMove(e));
            this.mapCanvas.addEventListener('mouseleave', () => this.onMouseLeave());
            this.mapCanvas.addEventListener('click',      e => this.onMapClick(e));
        }

        this.initDropZone();
        this.refresh();
    }

    /** Wire up the ATT file drop zone in the sidebar. */
    private initDropZone(): void {
        const fileInput = document.getElementById('att-file-input') as HTMLInputElement | null;
        const dropZone  = document.getElementById('att-drop-zone');

        fileInput?.addEventListener('change', () => {
            const file = fileInput.files?.[0];
            if (file) void this.loadFile(file);
            fileInput.value = '';
        });

        if (!dropZone) return;
        dropZone.addEventListener('click', () => fileInput?.click());
        dropZone.addEventListener('dragover', e => {
            e.preventDefault();
            dropZone.classList.add('drop-zone--active');
        });
        dropZone.addEventListener('dragleave', e => {
            if (!dropZone.contains(e.relatedTarget as Node)) {
                dropZone.classList.remove('drop-zone--active');
            }
        });
        dropZone.addEventListener('drop', e => {
            e.preventDefault();
            dropZone.classList.remove('drop-zone--active');
            const file = e.dataTransfer?.files[0];
            if (file?.name.toLowerCase().endsWith('.att')) void this.loadFile(file);
        });
    }

    /** Load an ATT file directly (without going through the World tab). */
    async loadFile(file: File): Promise<void> {
        try {
            const buf  = await file.arrayBuffer();
            const data = readATT(buf);
            this.loadedFileName = file.name;
            this.attData        = data;
            this.worldNumber    = null;
            this.summary        = summarizeTerrainAttributeData(data);
            this.hiddenFlags.clear();
            this.baseDirty = true;
            this.refresh();
        } catch (err) {
            const msg = err instanceof Error ? err.message : String(err);
            if (this.statusEl) this.statusEl.textContent = `Failed to load: ${msg}`;
        }
    }

    /** Called when a world is loaded (or unloaded) in TerrainScene. */
    setData(data: TerrainAttributeData | null, worldNumber: number | null): void {
        this.attData        = data;
        this.worldNumber    = worldNumber;
        this.loadedFileName = null;   // world-sourced data, clear any file name
        this.summary        = data ? summarizeTerrainAttributeData(data) : null;
        this.hiddenFlags.clear();
        this.baseDirty = true;
        this.refresh();
    }

    // ------------------------------------------------------------------
    // Rendering pipeline
    // ------------------------------------------------------------------

    private refresh(): void {
        const hasData = this.attData !== null;

        this.noDataEl?.classList.toggle('hidden', hasData);
        this.mapWrapEl?.classList.toggle('hidden', !hasData);

        this.renderMeta();
        this.renderLegend();

        if (hasData) {
            this.renderBaseCanvas();
            this.compositeToMapCanvas();
        }
    }

    /** Render the 256×256 base image from ATT data into the offscreen buffer. */
    private renderBaseCanvas(): void {
        if (!this.baseDirty || !this.attData) return;
        const buf = this.baseImageData.data;
        const tw  = this.attData.terrainWall;

        for (let i = 0; i < TERRAIN_SIZE * TERRAIN_SIZE; i++) {
            const value = tw[i];
            const p = i * 4;

            if (value === 0) {
                buf[p]     = 10;
                buf[p + 1] = 16;
                buf[p + 2] = 26;
                buf[p + 3] = 255;
                continue;
            }

            let r = 0, g = 0, b = 0, n = 0;
            for (const def of TERRAIN_ATTRIBUTE_FLAG_DEFINITIONS) {
                if ((value & def.flag) === 0) continue;
                if (this.hiddenFlags.has(def.flag)) continue;
                const c = FLAG_COLOR_MAP.get(def.flag)!;
                r += c[0]; g += c[1]; b += c[2];
                n++;
            }

            if (n > 0) {
                buf[p]     = Math.round(r / n);
                buf[p + 1] = Math.round(g / n);
                buf[p + 2] = Math.round(b / n);
                buf[p + 3] = 255;
            } else {
                // tile has flags but all are hidden
                buf[p]     = 22;
                buf[p + 1] = 32;
                buf[p + 2] = 48;
                buf[p + 3] = 255;
            }
        }

        this.offscreenCtx.putImageData(this.baseImageData, 0, 0);
        this.baseDirty = false;
    }

    /** Composite offscreen + overlay onto the visible map canvas. */
    private compositeToMapCanvas(): void {
        if (!this.mapCanvas || !this.attData) return;
        const ctx = this.mapCanvas.getContext('2d');
        if (!ctx) return;

        const w = this.mapCanvas.width;
        const h = this.mapCanvas.height;

        ctx.imageSmoothingEnabled = false;
        ctx.clearRect(0, 0, w, h);
        ctx.drawImage(this.offscreenCanvas, 0, 0, w, h);
        ctx.drawImage(this.overlayCanvas,   0, 0, w, h);
    }

    // ------------------------------------------------------------------
    // Mouse interaction
    // ------------------------------------------------------------------

    private onMouseMove(e: MouseEvent): void {
        const tile = this.getTileCoords(e);
        if (!tile) {
            this.clearOverlay();
            this.hideTooltip();
            this.lastHoverTile = null;
            return;
        }

        if (this.lastHoverTile?.x !== tile.x || this.lastHoverTile?.y !== tile.y) {
            this.lastHoverTile = tile;
            this.drawHoverOverlay(tile.x, tile.y);
            this.compositeToMapCanvas();
        }

        this.showTooltip(tile.x, tile.y, e.clientX, e.clientY);
    }

    private onMouseLeave(): void {
        this.lastHoverTile = null;
        this.clearOverlay();
        this.compositeToMapCanvas();
        this.hideTooltip();
    }

    private onMapClick(e: MouseEvent): void {
        const tile = this.getTileCoords(e);
        if (!tile || !this.attData) return;
        const value = this.attData.terrainWall[tile.y * TERRAIN_SIZE + tile.x];
        this.onTileClicked?.(tile.x, tile.y, value);
    }

    private getTileCoords(e: MouseEvent): { x: number; y: number } | null {
        if (!this.mapCanvas) return null;
        const rect  = this.mapCanvas.getBoundingClientRect();
        const scaleX = TERRAIN_SIZE / rect.width;
        const scaleY = TERRAIN_SIZE / rect.height;
        const x = Math.floor((e.clientX - rect.left)  * scaleX);
        const y = Math.floor((e.clientY - rect.top)   * scaleY);
        if (x < 0 || x >= TERRAIN_SIZE || y < 0 || y >= TERRAIN_SIZE) return null;
        return { x, y };
    }

    // ------------------------------------------------------------------
    // Overlay (hover highlight + crosshair)
    // ------------------------------------------------------------------

    private drawHoverOverlay(tx: number, ty: number): void {
        const ctx = this.overlayCtx;
        const S   = TERRAIN_SIZE;
        ctx.clearRect(0, 0, S, S);

        // Crosshair lines (subtle)
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth   = 0.5;
        ctx.beginPath();
        ctx.moveTo(tx + 0.5, 0); ctx.lineTo(tx + 0.5, S);
        ctx.moveTo(0, ty + 0.5); ctx.lineTo(S,  ty + 0.5);
        ctx.stroke();

        // Highlighted tile
        ctx.fillStyle = 'rgba(255,255,255,0.45)';
        ctx.fillRect(tx, ty, 1, 1);

        // Small border around tile (offset 1px to stay visible)
        ctx.strokeStyle = 'rgba(255,255,255,0.85)';
        ctx.lineWidth   = 0.25;
        ctx.strokeRect(tx, ty, 1, 1);
    }

    private clearOverlay(): void {
        this.overlayCtx.clearRect(0, 0, TERRAIN_SIZE, TERRAIN_SIZE);
    }

    // ------------------------------------------------------------------
    // Tooltip
    // ------------------------------------------------------------------

    private showTooltip(tx: number, ty: number, clientX: number, clientY: number): void {
        if (!this.tooltipEl || !this.attData) return;

        const idx   = ty * TERRAIN_SIZE + tx;
        const value = this.attData.terrainWall[idx];
        const names = describeTerrainAttributeFlags(value);

        let html = `
            <div class="att-tip-header">
                <span class="att-tip-coord">(${tx}, ${ty})</span>
                <span class="att-tip-hex">${formatTerrainAttributeFlagHex(value)}</span>
            </div>`;

        if (names.length > 0) {
            html += '<div class="att-tip-flags">';
            for (const name of names) {
                const def = TERRAIN_ATTRIBUTE_FLAG_DEFINITIONS.find(d => d.name === name);
                const css = def ? getAttFlagColorCss(def.flag) : '#888';
                html += `<span class="att-tip-flag" style="--c:${css}">${name}</span>`;
            }
            html += '</div>';
        } else {
            html += '<div class="att-tip-empty">No flags set</div>';
        }

        this.tooltipEl.innerHTML = html;
        this.tooltipEl.classList.remove('hidden');

        // Smart positioning: keep inside viewport
        const margin = 14;
        const tw = this.tooltipEl.offsetWidth  || 180;
        const th = this.tooltipEl.offsetHeight || 80;

        let left = clientX + margin;
        let top  = clientY + margin;
        if (left + tw > window.innerWidth  - margin) left = clientX - tw - margin;
        if (top  + th > window.innerHeight - margin) top  = clientY - th - margin;

        this.tooltipEl.style.left = `${left}px`;
        this.tooltipEl.style.top  = `${top}px`;
    }

    private hideTooltip(): void {
        this.tooltipEl?.classList.add('hidden');
    }

    // ------------------------------------------------------------------
    // Sidebar: meta table
    // ------------------------------------------------------------------

    private renderMeta(): void {
        if (!this.metaEl) return;
        const s = this.summary;

        const set = (id: string, text: string) => {
            const el = document.getElementById(id);
            if (el) el.textContent = text;
        };

        if (!s) {
            set('att-meta-world',    '-');
            set('att-meta-version',  '-');
            set('att-meta-format',   '-');
            set('att-meta-tiles',    '-');
            set('att-meta-flagged',  '-');
            if (this.statusEl) this.statusEl.textContent = 'No ATT data. Load a world or drop an ATT file.';
            return;
        }

        const worldLabel = this.loadedFileName ? `File` : `${this.worldNumber ?? '-'}`;
        set('att-meta-world',   worldLabel);
        set('att-meta-version', `${s.version}`);
        set('att-meta-format',  s.formatLabel);
        set('att-meta-tiles',   s.tileCount.toLocaleString());
        set('att-meta-flagged', `${s.occupiedTileCount.toLocaleString()} (${((s.occupiedTileCount / s.tileCount) * 100).toFixed(1)}%)`);

        if (this.statusEl) {
            this.statusEl.textContent = this.loadedFileName
                ? `${this.loadedFileName} · ${s.formatLabel}`
                : `World ${this.worldNumber} · ${s.formatLabel}`;
        }
    }

    // ------------------------------------------------------------------
    // Sidebar: legend / filter
    // ------------------------------------------------------------------

    private renderLegend(): void {
        if (!this.legendEl) return;
        if (!this.summary) {
            this.legendEl.innerHTML = '';
            return;
        }

        this.legendEl.replaceChildren(...this.summary.flags.map(f => this.buildLegendItem(f)));
    }

    private buildLegendItem(flag: TerrainAttributeFlagSummary): HTMLElement {
        const color   = getAttFlagColor(flag.flag);
        const colorCss = `rgb(${color[0]},${color[1]},${color[2]})`;
        const hidden  = this.hiddenFlags.has(flag.flag);

        const row = document.createElement('div');
        row.className = [
            'att-legend-row',
            !flag.active ? 'att-legend-row--inactive' : '',
            hidden       ? 'att-legend-row--hidden'   : '',
        ].filter(Boolean).join(' ');

        // Eye toggle button
        const toggle = document.createElement('button');
        toggle.type      = 'button';
        toggle.className = 'att-legend-toggle';
        toggle.title     = hidden ? 'Show on map' : 'Hide from map';
        toggle.innerHTML = hidden
            ? `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>`
            : `<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>`;

        if (flag.active) {
            toggle.addEventListener('click', () => {
                if (this.hiddenFlags.has(flag.flag)) {
                    this.hiddenFlags.delete(flag.flag);
                } else {
                    this.hiddenFlags.add(flag.flag);
                }
                this.baseDirty = true;
                this.renderBaseCanvas();
                this.compositeToMapCanvas();
                this.renderLegend();
            });
        } else {
            toggle.disabled = true;
        }

        // Colored swatch
        const swatch = document.createElement('span');
        swatch.className      = 'att-legend-swatch';
        swatch.style.background = colorCss;

        // Name
        const name = document.createElement('span');
        name.className   = 'att-legend-name';
        name.textContent = flag.name;

        // Count
        const count = document.createElement('span');
        count.className   = 'att-legend-count';
        count.textContent = flag.active ? flag.count.toLocaleString() : '—';

        // Hex
        const hex = document.createElement('span');
        hex.className   = 'att-legend-hex';
        hex.textContent = flag.hex;

        row.append(toggle, swatch, name, count, hex);
        return row;
    }
}
