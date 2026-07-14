import { decodeOzg, decodeOzd } from './ozg-cryptor';
import {
  buildSwfDisplayList,
  collectSubImages,
  extractBitmaps,
  parseDefineSprites,
  parseShapeBitmapRefs,
  parseSwfBody,
  parseExternalImages,
} from './swf-reader';
import type {
  SwfTag,
  SwfFrameInfo,
  ExternalImageRef,
  SubImageRef,
  SwfDisplayObject,
  SwfShapeBitmapRef,
  SwfSpriteDefinition,
} from './swf-reader';
import { decodeDdsToRgba } from './dds-decoder';
import { getFilePathFromFile, readExistingFilesFromPaths } from '../electron-helper';

interface LoadedTexture {
  name: string;
  width: number;
  height: number;
  format: string;
  canvas: HTMLCanvasElement;
  charId?: number;
  /** Original filename from the GFx external-image tag, lower-cased. */
  refFileName?: string;
  source: 'embedded' | 'ozd' | 'subimage';
}

export class GfxBrowser {
  private statusEl: HTMLElement | null = null;
  private statsEl: HTMLElement | null = null;
  private tagBodyEl: HTMLElement | null = null;
  private galleryEl: HTMLElement | null = null;
  private detailEl: HTMLElement | null = null;
  private stageWrapEl: HTMLElement | null = null;
  private stageScrollEl: HTMLElement | null = null;
  private stageCanvasEl: HTMLCanvasElement | null = null;
  private stageNoteEl: HTMLElement | null = null;
  private clearBtn: HTMLElement | null = null;
  private searchInput: HTMLInputElement | null = null;
  private showTagsToggle: HTMLInputElement | null = null;

  private allTags: SwfTag[] = [];
  private externalImages: ExternalImageRef[] = [];
  private subImages = new Map<number, SubImageRef>();
  private shapeBitmapRefs = new Map<number, SwfShapeBitmapRef[]>();
  private spriteDefinitions = new Map<number, SwfSpriteDefinition>();
  private textures = new Map<string, LoadedTexture>();
  private ozgInfo: { name: string; version: number; frame: SwfFrameInfo } | null = null;
  private searchQuery = '';
  private showTagTable = false;
  private stageNoteBase = '';

  private stageZoom = 1;
  private stagePanActive = false;
  private stagePanPointerId = -1;
  private stagePanStart = { x: 0, y: 0, scrollLeft: 0, scrollTop: 0 };
  private static readonly MIN_ZOOM = 0.1;
  private static readonly MAX_ZOOM = 16;

  init(): void {
    this.statusEl  = document.getElementById('gfx-status-bar');
    this.statsEl   = document.getElementById('gfx-stats');
    this.tagBodyEl = document.getElementById('gfx-tag-body');
    this.galleryEl = document.getElementById('gfx-bitmap-gallery');
    this.detailEl  = document.getElementById('gfx-detail');
    this.stageWrapEl = document.getElementById('gfx-stage-wrap');
    this.stageScrollEl = this.stageWrapEl?.querySelector('.gfx-stage-scroll') as HTMLElement | null;
    this.stageCanvasEl = document.getElementById('gfx-stage-canvas') as HTMLCanvasElement | null;
    this.stageNoteEl = document.getElementById('gfx-stage-note');
    this.clearBtn  = document.getElementById('gfx-clear-btn');
    this.searchInput = document.getElementById('gfx-search') as HTMLInputElement | null;
    this.showTagsToggle = document.getElementById('gfx-show-tags-toggle') as HTMLInputElement | null;

    this.bindLoadControls();

    this.clearBtn?.addEventListener('click', () => this.clearAll());
    this.searchInput?.addEventListener('input', () => {
      this.searchQuery = this.searchInput!.value;
      this.renderTagList();
      this.renderGallery();
    });
    this.showTagsToggle?.addEventListener('change', () => {
      this.showTagTable = this.showTagsToggle?.checked ?? false;
      this.renderTagList();
    });

    this.bindStageInteractions();
  }

  private bindLoadControls(): void {
    const ozgDropZone = document.getElementById('gfx-ozg-drop');
    const ozdDropZone = document.getElementById('gfx-ozd-drop');
    const ozgFileInput = document.getElementById('gfx-ozg-file-input') as HTMLInputElement | null;
    const ozgFolderInput = document.getElementById('gfx-ozg-folder-input') as HTMLInputElement | null;
    const ozdFileInput = document.getElementById('gfx-ozd-file-input') as HTMLInputElement | null;
    const ozdFolderInput = document.getElementById('gfx-ozd-folder-input') as HTMLInputElement | null;

    document.getElementById('gfx-ozg-file-btn')?.addEventListener('click', () => this.openInput(ozgFileInput));
    document.getElementById('gfx-ozg-folder-btn')?.addEventListener('click', () => this.openInput(ozgFolderInput));
    document.getElementById('gfx-ozd-file-btn')?.addEventListener('click', () => this.openInput(ozdFileInput));
    document.getElementById('gfx-ozd-folder-btn')?.addEventListener('click', () => this.openInput(ozdFolderInput));

    this.bindInput(ozgFileInput, files => this.loadOzgRender(files));
    this.bindInput(ozgFolderInput, files => this.loadOzgRender(files));
    this.bindInput(ozdFileInput, files => this.loadOzdGallery(files));
    this.bindInput(ozdFolderInput, files => this.loadOzdGallery(files));

    this.wireDropZone(ozgDropZone, () => this.openInput(ozgFileInput), files => this.loadOzgRender(files));
    this.wireDropZone(ozdDropZone, () => this.openInput(ozdFileInput), files => this.loadOzdGallery(files));
  }

  private openInput(input: HTMLInputElement | null): void {
    if (!input) return;
    input.value = '';
    input.click();
  }

  private bindInput(
    input: HTMLInputElement | null,
    onFiles: (files: File[]) => Promise<void>,
  ): void {
    input?.addEventListener('change', () => {
      const files = input.files ? Array.from(input.files) : [];
      input.value = '';
      if (files.length > 0) void onFiles(files);
    });
  }

  private wireDropZone(
    zone: HTMLElement | null,
    onClick: () => void,
    onDrop: (files: File[]) => Promise<void>,
  ): void {
    if (!zone) return;

    zone.addEventListener('click', onClick);
    zone.addEventListener('dragover', e => {
      e.preventDefault();
      zone.classList.add('drag-over');
    });
    zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
    zone.addEventListener('drop', async (e) => {
      e.preventDefault();
      zone.classList.remove('drag-over');
      const files = await collectDroppedFiles(e);
      if (files.length > 0) void onDrop(files);
    });
  }

  private bindStageInteractions(): void {
    const scroll = this.stageScrollEl;
    const canvas = this.stageCanvasEl;
    if (!scroll || !canvas) return;

    scroll.addEventListener('wheel', (e) => this.handleStageWheel(e), { passive: false });

    canvas.addEventListener('pointerdown', (e) => this.handleStagePanStart(e));
    canvas.addEventListener('pointermove', (e) => this.handleStagePanMove(e));
    canvas.addEventListener('pointerup', (e) => this.handleStagePanEnd(e));
    canvas.addEventListener('pointercancel', (e) => this.handleStagePanEnd(e));
    canvas.addEventListener('dblclick', () => this.resetStageView());
  }

  private handleStageWheel(e: WheelEvent): void {
    const scroll = this.stageScrollEl;
    const canvas = this.stageCanvasEl;
    if (!scroll || !canvas || !canvas.width || !canvas.height) return;

    e.preventDefault();

    const rect = canvas.getBoundingClientRect();
    const factor = e.deltaY < 0 ? 1.15 : 1 / 1.15;
    // At zoom=1, CSS max-width:100% may shrink the canvas below its intrinsic
    // size. Re-baseline to the actual display scale so the first zoom step is
    // a smooth visual increment rather than a jump to intrinsic × factor.
    const actualDisplayScale = rect.width > 0 ? rect.width / canvas.width : this.stageZoom;
    const prevZoom = Math.abs(this.stageZoom - 1) < 1e-6 ? actualDisplayScale : this.stageZoom;
    const nextZoom = Math.max(GfxBrowser.MIN_ZOOM, Math.min(GfxBrowser.MAX_ZOOM, prevZoom * factor));
    if (nextZoom === prevZoom) return;

    const pointOnCanvasX = (e.clientX - rect.left) / actualDisplayScale;
    const pointOnCanvasY = (e.clientY - rect.top) / actualDisplayScale;

    this.stageZoom = nextZoom;
    this.applyStageZoom();

    // Re-anchor: after re-layout, shift scroll so the source pixel lands under the cursor.
    const newRect = canvas.getBoundingClientRect();
    scroll.scrollLeft += newRect.left - e.clientX + pointOnCanvasX * nextZoom;
    scroll.scrollTop += newRect.top - e.clientY + pointOnCanvasY * nextZoom;
  }

  private handleStagePanStart(e: PointerEvent): void {
    const scroll = this.stageScrollEl;
    const canvas = this.stageCanvasEl;
    if (!scroll || !canvas) return;
    if (e.button !== 0) return;

    this.stagePanActive = true;
    this.stagePanPointerId = e.pointerId;
    this.stagePanStart = {
      x: e.clientX,
      y: e.clientY,
      scrollLeft: scroll.scrollLeft,
      scrollTop: scroll.scrollTop,
    };
    canvas.setPointerCapture(e.pointerId);
    canvas.style.cursor = 'grabbing';
  }

  private handleStagePanMove(e: PointerEvent): void {
    if (!this.stagePanActive || e.pointerId !== this.stagePanPointerId) return;
    const scroll = this.stageScrollEl;
    if (!scroll) return;
    scroll.scrollLeft = this.stagePanStart.scrollLeft - (e.clientX - this.stagePanStart.x);
    scroll.scrollTop = this.stagePanStart.scrollTop - (e.clientY - this.stagePanStart.y);
  }

  private handleStagePanEnd(e: PointerEvent): void {
    if (!this.stagePanActive || e.pointerId !== this.stagePanPointerId) return;
    this.stagePanActive = false;
    this.stagePanPointerId = -1;
    const canvas = this.stageCanvasEl;
    if (canvas) {
      if (canvas.hasPointerCapture(e.pointerId)) canvas.releasePointerCapture(e.pointerId);
      canvas.style.cursor = '';
    }
  }

  private resetStageView(): void {
    this.stageZoom = 1;
    this.applyStageZoom();
    const scroll = this.stageScrollEl;
    if (scroll) {
      scroll.scrollLeft = 0;
      scroll.scrollTop = 0;
    }
  }

  private applyStageZoom(): void {
    const canvas = this.stageCanvasEl;
    if (!canvas) return;

    if (this.stageZoom === 1) {
      canvas.style.width = '';
      canvas.style.height = '';
      canvas.style.maxWidth = '';
      canvas.style.maxHeight = '';
    } else {
      canvas.style.width = `${canvas.width * this.stageZoom}px`;
      canvas.style.height = `${canvas.height * this.stageZoom}px`;
      canvas.style.maxWidth = 'none';
      canvas.style.maxHeight = 'none';
    }
    this.updateStageNote();
  }

  private updateStageNote(): void {
    if (!this.stageNoteEl) return;
    const zoomPct = Math.round(this.stageZoom * 100);
    const hint = 'Scroll to zoom, drag to pan, double-click to reset';
    this.stageNoteEl.textContent = this.stageNoteBase
      ? `${this.stageNoteBase}  \u2502  Zoom: ${zoomPct}%  \u2502  ${hint}.`
      : '';
  }

  private async loadOzgRender(files: File[]): Promise<void> {
    const ozgFiles = files
      .filter(file => /\.(ozg|swf|gfx)$/i.test(file.name))
      .sort((a, b) => a.name.localeCompare(b.name));
    const ozdFiles = files
      .filter(file => /\.ozd$/i.test(file.name))
      .sort((a, b) => a.name.localeCompare(b.name));

    if (ozgFiles.length === 0) {
      this.setStatus('No OZG/GFX/SWF render file found.');
      return;
    }

    const renderFile = ozgFiles[0];
    this.clearAll();
    console.log(`[GfxBrowser] Loading OZG render ${renderFile.name}`);
    this.setStatus(`Loading ${renderFile.name}\u2026`);
    this.stageZoom = 1;
    this.applyStageZoom();

    try {
      const bytes = new Uint8Array(await renderFile.arrayBuffer());
      const textureHints = await this.processOzg(renderFile.name, bytes, renderFile.name.toLowerCase().endsWith('.ozg'));
      const queuedOzdNames = new Set(ozdFiles.map(f => f.name.toLowerCase()));
      const autoOzdFiles = await this.loadElectronSiblingOzdFiles(renderFile, textureHints, queuedOzdNames);

      for (const file of [...ozdFiles, ...autoOzdFiles]) {
        await this.tryProcessOzdFile(file);
      }
    } catch (err) {
      console.error(`[GfxBrowser] ${renderFile.name}:`, err);
      this.setStatus(`Failed to load ${renderFile.name}.`);
      return;
    }

    if (ozgFiles.length > 1) {
      console.log(`[GfxBrowser] Folder contained ${ozgFiles.length} render files; displayed ${renderFile.name}`);
    }

    this.renderAll();
  }

  private async loadOzdGallery(files: File[]): Promise<void> {
    const ozdFiles = files
      .filter(file => /\.ozd$/i.test(file.name))
      .sort((a, b) => a.name.localeCompare(b.name));

    if (ozdFiles.length === 0) {
      this.setStatus('No OZD files found.');
      return;
    }

    this.clearAll();
    console.log(`[GfxBrowser] Loading ${ozdFiles.length} OZD image file(s)`);
    this.setStatus(`Loading ${ozdFiles.length} OZD image file(s)\u2026`);

    for (const file of ozdFiles) {
      await this.tryProcessOzdFile(file);
    }

    this.renderAll();
  }

  private async tryProcessOzdFile(file: File): Promise<void> {
    try {
      const bytes = new Uint8Array(await file.arrayBuffer());
      this.processOzd(file.name, bytes);
    } catch (err) {
      console.error(`[GfxBrowser] ${file.name}:`, err);
    }
  }

  private async processOzg(
    name: string,
    bytes: Uint8Array,
    decrypt: boolean,
  ): Promise<{ exportedImageCount: number; bitmapIds: Set<number> }> {
    let swfBody: Uint8Array;
    let swfVer = 0;

    if (decrypt) {
      const result = await decodeOzg(bytes);
      swfBody = result.swfBody;
      swfVer = result.swfVersion;
    } else {
      swfVer = bytes[3];
      swfBody = bytes.slice(8);
      const sig = String.fromCharCode(bytes[0], bytes[1], bytes[2]);
      if (sig === 'CWS' || sig === 'CFX') {
        const ds = new DecompressionStream('deflate');
        const w = ds.writable.getWriter();
        const r = ds.readable.getReader();
        void w.write(swfBody.slice()).then(() => w.close());
        const chunks: Uint8Array[] = [];
        for (;;) { const { done, value } = await r.read(); if (done) break; if (value) chunks.push(value); }
        const total = chunks.reduce((s, c) => s + c.length, 0);
        swfBody = new Uint8Array(total);
        let i = 0; for (const c of chunks) { swfBody.set(c, i); i += c.length; }
      }
    }

    const parsed = parseSwfBody(swfBody);
    console.log(`[GfxBrowser] ${name}: ${parsed.tags.length} tags, ${parsed.frame.widthPx}\u00d7${parsed.frame.heightPx}`);

    this.removeEmbeddedTextures();
    this.removeSubImageTextures();
    this.allTags = parsed.tags;
    this.externalImages = parseExternalImages(parsed.tags);
    this.spriteDefinitions = parseDefineSprites(parsed.tags);
    this.subImages = collectSubImages(parsed.tags, this.spriteDefinitions);
    this.shapeBitmapRefs = collectShapeBitmapRefs(parsed.tags, this.spriteDefinitions);
    this.ozgInfo = { name, version: swfVer, frame: parsed.frame };

    const bitmaps = await extractBitmaps(parsed.tags);
    for (const bitmap of bitmaps) {
      const canvas = document.createElement('canvas');
      await bitmap.draw(canvas);
      this.textures.set(`embedded:${bitmap.charId}`, {
        name: `${bitmap.tagName} #${bitmap.charId}`,
        width: bitmap.width,
        height: bitmap.height,
        format: bitmap.format,
        canvas,
        charId: bitmap.charId,
        source: 'embedded',
      });
    }

    if (this.externalImages.length) {
      console.log(`[GfxBrowser] External images: ${this.externalImages.map(r => `charId=${r.charId}→${r.fileName}`).join(', ')}`);
    }
    if (this.subImages.size) {
      console.log(`[GfxBrowser] Sub-images: ${this.subImages.size} atlas rect(s)`);
    }

    return {
      exportedImageCount: countExportedImageAssets(parsed.tags),
      bitmapIds: collectExternalShapeBitmapIds(this.shapeBitmapRefs, collectDefinedBitmapIds(parsed.tags), this.subImages),
    };
  }

  private async loadElectronSiblingOzdFiles(
    file: File,
    textureHints: { exportedImageCount: number; bitmapIds: Set<number> },
    queuedOzdNames: Set<string>,
  ): Promise<File[]> {
    const filePath = getFilePathFromFile(file);
    if (!filePath) return [];

    const slash = Math.max(filePath.lastIndexOf('/'), filePath.lastIndexOf('\\'));
    if (slash < 0) return [];

    const dir = filePath.slice(0, slash + 1);
    const baseName = file.name.replace(/\.[^.]+$/, '');
    const texturePaths: string[] = [];
    const queueName = (name: string): void => {
      const key = name.toLowerCase();
      if (queuedOzdNames.has(key)) return;
      queuedOzdNames.add(key);
      texturePaths.push(`${dir}${name}`);
    };

    // Preferred: explicit filenames from GFx external-image tags. The exporter
    // writes e.g. "Chat_I5.dds" inside the SWF, but the decrypted file on disk
    // uses .ozd — try both extensions.
    for (const ref of this.externalImages) {
      if (!ref.fileName) continue;
      const base = ref.fileName.replace(/\.[^.]+$/, '');
      queueName(`${base}.ozd`);
      queueName(ref.fileName);
    }

    // Fallback: sibling atlases referenced by charId but without an explicit
    // filename (older GFx variants). `_I{id}` uses decimal *or* hex (MU's
    // `main_IE.ozd` = charId 14), so try both encodings.
    const ids = new Set<number>();
    for (let i = 1; i <= textureHints.exportedImageCount; i++) ids.add(i);
    for (const id of textureHints.bitmapIds) ids.add(id);
    for (const id of [...ids].sort((a, b) => a - b)) {
      queueName(`${baseName}_I${id}.ozd`);
      if (id >= 10) queueName(`${baseName}_I${id.toString(16).toUpperCase()}.ozd`);
    }

    if (!texturePaths.length) return [];

    const files = (await readExistingFilesFromPaths(texturePaths))
      .map(data => new File([data.data], data.name, { type: 'application/octet-stream' }));

    if (files.length > 0) {
      console.log(`[GfxBrowser] Auto-loaded ${files.length} sibling OZD texture(s) for ${file.name}`);
    }

    return files;
  }

  private processOzd(name: string, bytes: Uint8Array): void {
    const { width, height, format, compressedData } = decodeOzd(bytes);

    if (format === 'unknown') {
      console.warn(`[GfxBrowser] ${name}: unsupported DDS format, skipping`);
      return;
    }

    const rgba = decodeDdsToRgba(width, height, format, compressedData);
    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;
    ctx.putImageData(new ImageData(new Uint8ClampedArray(rgba), width, height), 0, 0);

    const charId = this.resolveTextureCharId(name);
    console.log(`[GfxBrowser] ${name}: ${width}\u00d7${height} ${format}${charId !== undefined ? ` (charId=${charId})` : ''}`);
    this.textures.set(name, {
      name,
      width,
      height,
      format,
      canvas,
      charId,
      refFileName: name.toLowerCase(),
      source: 'ozd',
    });

    if (charId !== undefined) this.materializeSubImagesFor(charId);
  }

  // Tries to bind a just-loaded OZD file to a SWF charId: first via explicit
  // GFx_DefineExternalImage filenames, then via the legacy `_I{id}` suffix.
  // If the SWF declares any external image names, the regex fallback is skipped
  // so that orphan sibling files on disk don't shadow the referenced atlas.
  private resolveTextureCharId(fileName: string): number | undefined {
    const lower = fileName.toLowerCase();
    const baseNoExt = lower.replace(/\.[^.]+$/, '');

    for (const ref of this.externalImages) {
      if (!ref.fileName) continue;
      const refLower = ref.fileName.toLowerCase();
      const refBase = refLower.replace(/\.[^.]+$/, '');
      if (refLower === lower || refBase === baseNoExt) return ref.charId;
    }

    const hasNamedRefs = this.externalImages.some(r => r.fileName);
    if (hasNamedRefs) return undefined;

    const dec = /_I(\d+)\.ozd$/i.exec(fileName);
    if (dec) return Number(dec[1]);
    const hex = /_I([0-9A-F]+)\.ozd$/i.exec(fileName);
    if (hex) return parseInt(hex[1], 16);
    return undefined;
  }

  // For each sub-image anchored to `parentCharId`, draw its source rect from the
  // parent atlas into its own canvas and register it under the sub-image's
  // charId. Subsequent shape lookups can then fetch a texture directly.
  private materializeSubImagesFor(parentCharId: number): void {
    const parent = this.findExactTexture(parentCharId);
    if (!parent) return;

    for (const sub of this.subImages.values()) {
      if (sub.parentId !== parentCharId) continue;
      if (this.findExactTexture(sub.charId)) continue;

      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, sub.sourceWidth);
      canvas.height = Math.max(1, sub.sourceHeight);
      const ctx = canvas.getContext('2d');
      if (!ctx) continue;
      ctx.drawImage(
        parent.canvas,
        sub.sourceX, sub.sourceY, sub.sourceWidth, sub.sourceHeight,
        0, 0, sub.sourceWidth, sub.sourceHeight,
      );
      this.textures.set(`subimage:${sub.charId}`, {
        name: `${parent.name} [${sub.sourceX},${sub.sourceY} ${sub.sourceWidth}\u00d7${sub.sourceHeight}]`,
        width: sub.sourceWidth,
        height: sub.sourceHeight,
        format: parent.format,
        canvas,
        charId: sub.charId,
        source: 'subimage',
      });
    }
  }

  private findExactTexture(charId: number): LoadedTexture | undefined {
    for (const tex of this.textures.values()) {
      if (tex.charId === charId) return tex;
    }
    return undefined;
  }

  private renderAll(): void {
    const parts: string[] = [];
    if (this.ozgInfo) {
      const f = this.ozgInfo.frame;
      const fps = (f.fpsFixed88 / 256).toFixed(1);
      parts.push(`${this.ozgInfo.name}: SWF v${this.ozgInfo.version}, ${f.widthPx}\u00d7${f.heightPx}px, ${fps} FPS, ${this.allTags.length} tags`);
    }
    if (this.textures.size) parts.push(`${this.textures.size} texture(s)`);
    if (this.externalImages.length) parts.push(`${this.externalImages.length} ext. image refs`);

    if (this.statsEl) {
      this.statsEl.textContent = parts.join('  \u2502  ');
      this.statsEl.classList.toggle('hidden', !parts.length);
    }

    const hasContent = this.ozgInfo !== null || this.allTags.length > 0 || this.textures.size > 0;
    document.getElementById('gfx-no-data')?.classList.toggle('hidden', hasContent);
    this.galleryEl?.classList.toggle('gfx-bitmap-gallery--standalone', this.textures.size > 0 && this.allTags.length === 0 && !this.ozgInfo);

    this.renderStage();
    this.renderTagList();
    this.renderGallery();
    this.setStatus(parts.join(' | '));
  }

  private renderStage(): void {
    const canvas = this.stageCanvasEl;
    const wrap = this.stageWrapEl;
    if (!canvas || !wrap) return;

    const hasStageContent = this.allTags.length > 0 || this.ozgInfo !== null;
    wrap.classList.toggle('hidden', !hasStageContent);
    if (!hasStageContent) {
      const ctx = canvas.getContext('2d');
      ctx?.clearRect(0, 0, canvas.width, canvas.height);
      this.stageNoteBase = '';
      this.updateStageNote();
      return;
    }

    const frame = this.ozgInfo?.frame;
    const displayList = this.allTags.length ? buildSwfDisplayList(this.allTags) : [];
    const fallbackSize = this.getFallbackStageSize(displayList);
    const width = Math.max(1, frame?.widthPx || fallbackSize.width || 512);
    const height = Math.max(1, frame?.heightPx || fallbackSize.height || 384);
    canvas.width = width;
    canvas.height = height;
    this.applyStageZoom();

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);
    ctx.save();
    ctx.fillStyle = 'rgba(0, 0, 0, 0)';
    ctx.fillRect(0, 0, width, height);

    let drawn = 0;
    let missing = 0;
    let usedTextureOverview = false;
    if (displayList.length > 0) {
      for (const item of displayList) {
        const result = this.drawDisplayItem(ctx, item, new Set<number>());
        drawn += result.drawn;
        missing += result.missing;
      }

      if (drawn === 0 && this.textures.size > 0) {
        ctx.clearRect(0, 0, width, height);
        drawn = this.drawTextureOverview(ctx, width, height);
        usedTextureOverview = drawn > 0;
      }
    } else if (this.textures.size > 0) {
      drawn = this.drawTextureOverview(ctx, width, height);
      usedTextureOverview = drawn > 0;
    }
    ctx.restore();

    if (usedTextureOverview) {
      this.stageNoteBase = displayList.length > 0
        ? `No drawable placed images found; showing ${drawn} loaded image resource(s).`
        : `No placed frame objects found; showing ${drawn} loaded image resource(s).`;
    } else if (displayList.length > 0) {
      this.stageNoteBase = missing > 0
        ? `Rendered ${drawn} placed image(s), ${missing} missing texture file(s).`
        : `Rendered ${drawn} placed image(s).`;
    } else if (this.externalImages.length > 0) {
      this.stageNoteBase = `This GFx references external textures. Drop the matching .ozd files to render them.`;
    } else {
      this.stageNoteBase = `No renderable image resources found in this GFx.`;
    }
    this.updateStageNote();
  }

  private getFallbackStageSize(displayList: SwfDisplayObject[]): { width: number; height: number } {
    let width = 0;
    let height = 0;
    for (const item of displayList) {
      const texture = this.findTextureForCharId(item.charId);
      const ref = this.externalImages.find(r => r.charId === item.charId);
      const shapeRefs = this.shapeBitmapRefs.get(item.charId);
      const shapeWidth = shapeRefs?.reduce((max, shapeRef) => Math.max(max, shapeRef.bounds.xMax), 0) ?? 0;
      const shapeHeight = shapeRefs?.reduce((max, shapeRef) => Math.max(max, shapeRef.bounds.yMax), 0) ?? 0;
      const itemWidth = texture?.width ?? ref?.width ?? shapeWidth;
      const itemHeight = texture?.height ?? ref?.height ?? shapeHeight;
      width = Math.max(width, item.matrix.translateX + itemWidth * Math.abs(item.matrix.scaleX || 1));
      height = Math.max(height, item.matrix.translateY + itemHeight * Math.abs(item.matrix.scaleY || 1));
    }
    return { width: Math.ceil(width), height: Math.ceil(height) };
  }

  private drawDisplayItem(
    ctx: CanvasRenderingContext2D,
    item: SwfDisplayObject,
    spriteStack: Set<number>,
  ): { drawn: number; missing: number } {
    const m = item.matrix;
    let drawn = 0;
    let missing = 0;

    ctx.save();
    ctx.transform(m.scaleX, m.skew1, m.skew0, m.scaleY, m.translateX, m.translateY);

    const texture = this.findTextureForCharId(item.charId);
    if (texture) {
      ctx.drawImage(texture.canvas, 0, 0);
      drawn++;
      ctx.restore();
      return { drawn, missing };
    }

    const shapeRefs = this.shapeBitmapRefs.get(item.charId);
    if (shapeRefs?.length) {
      for (const shapeRef of shapeRefs) {
        const shapeTexture = this.findTextureForCharId(shapeRef.bitmapId);
        if (shapeTexture) {
          this.drawBitmapFill(ctx, shapeRef, shapeTexture);
          drawn++;
        } else {
          const ref = this.externalImages.find(r => r.charId === shapeRef.bitmapId);
          if (ref) {
            this.drawMissingImageMarker(ctx, shapeRef.bounds.xMin, shapeRef.bounds.yMin, shapeRef.bounds.width, shapeRef.bounds.height, ref.fileName || `char ${ref.charId}`);
            missing++;
          }
        }
      }
      ctx.restore();
      return { drawn, missing };
    }

    const sprite = this.spriteDefinitions.get(item.charId);
    if (sprite && !spriteStack.has(item.charId)) {
      const nestedStack = new Set(spriteStack);
      nestedStack.add(item.charId);
      for (const child of buildSwfDisplayList(sprite.tags)) {
        const childResult = this.drawDisplayItem(ctx, child, nestedStack);
        drawn += childResult.drawn;
        missing += childResult.missing;
      }
      ctx.restore();
      return { drawn, missing };
    }

    const ref = this.externalImages.find(r => r.charId === item.charId);
    if (ref) {
      this.drawMissingImageMarker(ctx, 0, 0, Math.max(1, ref.width), Math.max(1, ref.height), ref.fileName || `char ${ref.charId}`);
      missing++;
    }

    ctx.restore();
    return { drawn, missing };
  }

  private drawBitmapFill(ctx: CanvasRenderingContext2D, shapeRef: SwfShapeBitmapRef, tex: LoadedTexture): void {
    const bounds = shapeRef.bounds;
    const matrix = shapeRef.fillMatrix;

    ctx.save();
    ctx.beginPath();
    ctx.rect(bounds.xMin, bounds.yMin, Math.max(1, bounds.width), Math.max(1, bounds.height));
    ctx.clip();

    ctx.transform(
      matrix.scaleX / 20,
      matrix.skew1 / 20,
      matrix.skew0 / 20,
      matrix.scaleY / 20,
      matrix.translateX,
      matrix.translateY,
    );
    ctx.drawImage(tex.canvas, 0, 0);
    ctx.restore();
  }

  private drawMissingImageMarker(ctx: CanvasRenderingContext2D, x: number, y: number, width: number, height: number, label: string): void {
    ctx.fillStyle = 'rgba(248, 113, 113, 0.12)';
    ctx.strokeStyle = 'rgba(248, 113, 113, 0.7)';
    ctx.lineWidth = 1;
    ctx.fillRect(x, y, Math.max(1, width), Math.max(1, height));
    ctx.strokeRect(x + 0.5, y + 0.5, Math.max(1, width) - 1, Math.max(1, height) - 1);
    ctx.fillStyle = 'rgba(255, 230, 230, 0.92)';
    ctx.font = '12px monospace';
    ctx.fillText(label, x + 6, y + 16);
  }

  private drawTextureOverview(ctx: CanvasRenderingContext2D, width: number, height: number): number {
    const textures = [...this.textures.values()];
    if (textures.length === 0) return 0;

    const padding = 16;
    const tile = 128;
    const columns = Math.max(1, Math.floor((width - padding) / (tile + padding)));
    let drawn = 0;

    for (let i = 0; i < textures.length; i++) {
      const tex = textures[i];
      const col = i % columns;
      const row = Math.floor(i / columns);
      const x = padding + col * (tile + padding);
      const y = padding + row * (tile + 34);
      if (y > height) break;

      const scale = Math.min(tile / tex.width, tile / tex.height, 1);
      const drawWidth = tex.width * scale;
      const drawHeight = tex.height * scale;
      ctx.drawImage(tex.canvas, x + (tile - drawWidth) / 2, y + (tile - drawHeight) / 2, drawWidth, drawHeight);
      ctx.fillStyle = 'rgba(224, 232, 245, 0.85)';
      ctx.font = '11px monospace';
      ctx.fillText(tex.name.slice(0, 24), x, y + tile + 18);
      drawn++;
    }

    return drawn;
  }

  private renderTagList(): void {
    const tbody = this.tagBodyEl;
    if (!tbody) return;

    const tableWrapEl = document.getElementById('gfx-table-wrap');
    tableWrapEl?.classList.toggle('hidden', !this.showTagTable || this.allTags.length === 0);

    const q = this.searchQuery.trim().toLowerCase();
    const filtered = q
      ? this.allTags.filter(t => t.name.toLowerCase().includes(q) || String(t.type).includes(q))
      : this.allTags;

    const frag = document.createDocumentFragment();
    for (const tag of filtered) {
      if (tag.type === 0) continue;
      const tr = document.createElement('tr');
      tr.className = 'bmd-table-row';
      tr.innerHTML = `
        <td class="bmd-tc bmd-tc--id">${tag.type}</td>
        <td class="bmd-tc bmd-tc--name">${esc(tag.name)}</td>
        <td class="bmd-tc bmd-tc--size">${tag.length}</td>
        <td class="bmd-tc bmd-tc-offset">${tag.offset}</td>`;
      tr.addEventListener('click', () => this.showTagDetail(tag));
      frag.appendChild(tr);
    }
    tbody.innerHTML = '';
    tbody.appendChild(frag);
  }

  private renderGallery(): void {
    const gallery = this.galleryEl;
    if (!gallery) return;
    gallery.innerHTML = '';

    if (this.textures.size === 0) {
      gallery.classList.add('hidden');
      return;
    }
    gallery.classList.remove('hidden');

    const q = this.searchQuery.trim().toLowerCase();

    for (const [, tex] of this.textures) {
      if (q && !tex.name.toLowerCase().includes(q)) continue;

      const card = document.createElement('div');
      card.className = 'gfx-bitmap-card';

      const thumb = document.createElement('canvas');
      thumb.width = 96;
      thumb.height = 96;
      thumb.className = 'gfx-bitmap-thumb';
      const ctx = thumb.getContext('2d');
      if (ctx) {
        const scale = Math.min(96 / tex.width, 96 / tex.height);
        const w = tex.width * scale;
        const h = tex.height * scale;
        ctx.drawImage(tex.canvas, (96 - w) / 2, (96 - h) / 2, w, h);
      }
      card.appendChild(thumb);

      const info = document.createElement('div');
      info.className = 'gfx-bitmap-info';
      info.title = tex.name;
      info.textContent = `${tex.name.replace(/\.ozd$/i, '')}\n${tex.width}\u00d7${tex.height} ${tex.format}`;
      card.appendChild(info);

      card.addEventListener('click', () => this.showTextureDetail(tex));
      gallery.appendChild(card);
    }
  }

  private showTagDetail(tag: SwfTag): void {
    if (!this.detailEl) return;

    if (tag.type === 1003 || tag.type === 1007) {
      const ref = this.externalImages.find(r => {
        if (tag.data.length < 2) return false;
        return r.charId === (tag.data[0] | (tag.data[1] << 8));
      });
      if (ref) {
        this.showExternalImageDetail(tag, ref);
        return;
      }
    }

    const hex = Array.from(tag.data.slice(0, 64))
      .map(b => b.toString(16).padStart(2, '0'))
      .join(' ');
    this.detailEl.innerHTML = `
      <div class="bmd-detail-grid">
        <div class="bmd-detail-field"><span>Tag type</span><b>${tag.type}</b></div>
        <div class="bmd-detail-field"><span>Name</span><b>${esc(tag.name)}</b></div>
        <div class="bmd-detail-field"><span>Size</span><b>${tag.length} bytes</b></div>
        <div class="bmd-detail-field"><span>Offset</span><b>${tag.offset}</b></div>
      </div>
      ${tag.data.length > 0 ? `<div class="gfx-hex-preview">${hex}${tag.data.length > 64 ? ' \u2026' : ''}</div>` : ''}`;
    this.detailEl.classList.remove('hidden');
  }

  private showExternalImageDetail(tag: SwfTag, ref: ExternalImageRef): void {
    if (!this.detailEl) return;
    this.detailEl.innerHTML = '';

    const info = document.createElement('div');
    info.className = 'bmd-detail-grid';
    info.innerHTML = `
      <div class="bmd-detail-field"><span>Tag</span><b>${esc(tag.name)} (${tag.type})</b></div>
      <div class="bmd-detail-field"><span>Char ID</span><b>${ref.charId}</b></div>
      <div class="bmd-detail-field"><span>Size</span><b>${ref.width} \u00d7 ${ref.height}</b></div>
      <div class="bmd-detail-field"><span>Export</span><b>${esc(ref.exportName)}</b></div>
      <div class="bmd-detail-field"><span>File</span><b>${esc(ref.fileName)}</b></div>`;
    this.detailEl.appendChild(info);

    const tex = this.findMatchingTexture(ref);
    if (tex) {
      const preview = document.createElement('canvas');
      preview.className = 'gfx-bitmap-preview';
      preview.width = tex.width;
      preview.height = tex.height;
      const ctx = preview.getContext('2d');
      ctx?.drawImage(tex.canvas, 0, 0);
      this.detailEl.appendChild(preview);
    }

    this.detailEl.classList.remove('hidden');
  }

  private showTextureDetail(tex: LoadedTexture): void {
    if (!this.detailEl) return;
    this.detailEl.innerHTML = '';

    const info = document.createElement('div');
    info.className = 'bmd-detail-grid';
    info.innerHTML = `
      <div class="bmd-detail-field"><span>File</span><b>${esc(tex.name)}</b></div>
      <div class="bmd-detail-field"><span>Size</span><b>${tex.width} \u00d7 ${tex.height}</b></div>
      <div class="bmd-detail-field"><span>Format</span><b>DDS ${tex.format}</b></div>`;

    const ref = this.externalImages.find(r => this.findMatchingTexture(r) === tex);
    if (ref) {
      info.innerHTML += `
        <div class="bmd-detail-field"><span>Char ID</span><b>${ref.charId}</b></div>
        <div class="bmd-detail-field"><span>Export</span><b>${esc(ref.exportName)}</b></div>`;
    }
    this.detailEl.appendChild(info);

    const preview = document.createElement('canvas');
    preview.className = 'gfx-bitmap-preview';
    preview.width = tex.width;
    preview.height = tex.height;
    const ctx = preview.getContext('2d');
    ctx?.drawImage(tex.canvas, 0, 0);
    this.detailEl.appendChild(preview);

    this.detailEl.classList.remove('hidden');
  }

  private findMatchingTexture(ref: ExternalImageRef): LoadedTexture | undefined {
    const refBase = ref.fileName.replace(/\.[^.]+$/, '').toLowerCase();
    for (const [key, tex] of this.textures) {
      if (tex.source !== 'ozd') continue;
      const texBase = key.replace(/\.ozd$/i, '').toLowerCase();
      if (texBase === refBase || ref.fileName.toLowerCase() === key.toLowerCase()) return tex;
    }
    return undefined;
  }

  private findTextureForCharId(charId: number): LoadedTexture | undefined {
    const exact = this.findExactTexture(charId);
    if (exact) return exact;

    const ref = this.externalImages.find(r => r.charId === charId);
    if (ref) {
      const match = this.findMatchingTexture(ref);
      if (match) return match;
    }

    // Walk the sub-image parent chain in case the parent texture loaded after
    // `materializeSubImagesFor` ran or the sub-image is on disk independently.
    const sub = this.subImages.get(charId);
    if (sub) return this.findTextureForCharId(sub.parentId);
    return undefined;
  }

  private removeEmbeddedTextures(): void {
    for (const [key, texture] of this.textures) {
      if (texture.source === 'embedded') this.textures.delete(key);
    }
  }

  private removeSubImageTextures(): void {
    for (const [key, texture] of this.textures) {
      if (texture.source === 'subimage') this.textures.delete(key);
    }
  }

  private clearAll(): void {
    this.ozgInfo = null;
    this.allTags = [];
    this.externalImages = [];
    this.subImages.clear();
    this.shapeBitmapRefs.clear();
    this.spriteDefinitions.clear();
    this.textures.clear();
    this.searchQuery = '';
    this.showTagTable = false;
    if (this.searchInput) this.searchInput.value = '';
    if (this.showTagsToggle) this.showTagsToggle.checked = false;
    if (this.tagBodyEl) this.tagBodyEl.innerHTML = '';
    if (this.galleryEl) { this.galleryEl.innerHTML = ''; this.galleryEl.classList.add('hidden'); }
    this.galleryEl?.classList.remove('gfx-bitmap-gallery--standalone');
    if (this.detailEl) { this.detailEl.innerHTML = ''; this.detailEl.classList.add('hidden'); }
    if (this.stageWrapEl) this.stageWrapEl.classList.add('hidden');
    if (this.stageCanvasEl) {
      const ctx = this.stageCanvasEl.getContext('2d');
      ctx?.clearRect(0, 0, this.stageCanvasEl.width, this.stageCanvasEl.height);
    }
    this.stageZoom = 1;
    this.applyStageZoom();
    if (this.stageScrollEl) { this.stageScrollEl.scrollLeft = 0; this.stageScrollEl.scrollTop = 0; }
    this.stageNoteBase = '';
    if (this.stageNoteEl) this.stageNoteEl.textContent = '';
    if (this.statsEl) { this.statsEl.textContent = ''; this.statsEl.classList.add('hidden'); }
    document.getElementById('gfx-table-wrap')?.classList.add('hidden');
    document.getElementById('gfx-no-data')?.classList.remove('hidden');
    this.setStatus('');
  }

  private setStatus(msg: string): void {
    if (this.statusEl) this.statusEl.textContent = msg || 'GFx Browser';
  }
}

function esc(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function countExportedImageAssets(tags: SwfTag[]): number {
  let maxImageIndex = -1;

  for (const tag of tags) {
    if (tag.type !== 56 || tag.data.length < 2) continue;

    const count = tag.data[0] | (tag.data[1] << 8);
    let off = 2;
    for (let i = 0; i < count && off + 2 <= tag.data.length; i++) {
      off += 2;
      const nameStart = off;
      while (off < tag.data.length && tag.data[off] !== 0) off++;
      const name = new TextDecoder().decode(tag.data.subarray(nameStart, off));
      const match = /^image(\d+)$/i.exec(name);
      if (match) maxImageIndex = Math.max(maxImageIndex, Number(match[1]));
      if (off < tag.data.length) off++;
    }
  }

  return maxImageIndex + 1;
}

function collectExternalShapeBitmapIds(
  shapeBitmapRefs: Map<number, SwfShapeBitmapRef[]>,
  definedBitmapIds: Set<number>,
  subImages: Map<number, SubImageRef>,
): Set<number> {
  const ids = new Set<number>();

  for (const refs of shapeBitmapRefs.values()) {
    for (const ref of refs) {
      if (ref.bitmapId <= 0 || ref.bitmapId === 0xffff) continue;
      if (definedBitmapIds.has(ref.bitmapId)) continue;
      // Sub-images resolve through their parent texture — hint with the parent id instead.
      const sub = subImages.get(ref.bitmapId);
      ids.add(sub ? sub.parentId : ref.bitmapId);
    }
  }

  return ids;
}

function collectDefinedBitmapIds(tags: SwfTag[]): Set<number> {
  const ids = new Set<number>();

  for (const tag of tags) {
    if ((tag.type === 6 || tag.type === 20 || tag.type === 21 || tag.type === 35 || tag.type === 36 || tag.type === 37)
      && tag.data.length >= 2) {
      ids.add(tag.data[0] | (tag.data[1] << 8));
    } else if (tag.type === 39 && tag.data.length >= 4) {
      for (const id of collectDefinedBitmapIds(parseDefineSprites([tag]).get(tag.data[0] | (tag.data[1] << 8))?.tags ?? [])) {
        ids.add(id);
      }
    }
  }

  return ids;
}

function collectShapeBitmapRefs(
  rootTags: SwfTag[],
  spriteDefinitions: Map<number, SwfSpriteDefinition>,
): Map<number, SwfShapeBitmapRef[]> {
  const refs = parseShapeBitmapRefs(rootTags);

  for (const sprite of spriteDefinitions.values()) {
    const spriteRefs = parseShapeBitmapRefs(sprite.tags);
    for (const [shapeId, shapeRefs] of spriteRefs) {
      const existing = refs.get(shapeId) ?? [];
      refs.set(shapeId, [...existing, ...shapeRefs]);
    }
  }

  return refs;
}

async function collectDroppedFiles(e: DragEvent): Promise<File[]> {
  const items = e.dataTransfer?.items;
  if (!items) return e.dataTransfer?.files ? Array.from(e.dataTransfer.files) : [];

  const results: File[] = [];
  const pending: Promise<void>[] = [];

  for (let i = 0; i < items.length; i++) {
    const entry = items[i].webkitGetAsEntry?.();
    if (!entry) {
      const f = items[i].getAsFile();
      if (f) results.push(f);
      continue;
    }
    if (entry.isFile) {
      pending.push(new Promise<void>(res => (entry as FileSystemFileEntry).file(f => { results.push(f); res(); })));
    } else if (entry.isDirectory) {
      pending.push(readDirectory(entry as FileSystemDirectoryEntry, results));
    }
  }

  await Promise.all(pending);
  return results;
}

function readDirectory(dir: FileSystemDirectoryEntry, out: File[]): Promise<void> {
  return new Promise<void>(resolve => {
    const reader = dir.createReader();
    const batch = () => {
      reader.readEntries(async entries => {
        if (!entries.length) { resolve(); return; }
        const p: Promise<void>[] = [];
        for (const entry of entries) {
          if (entry.isFile) {
            p.push(new Promise<void>(r => (entry as FileSystemFileEntry).file(f => { out.push(f); r(); })));
          } else if (entry.isDirectory) {
            p.push(readDirectory(entry as FileSystemDirectoryEntry, out));
          }
        }
        await Promise.all(p);
        batch();
      }, () => resolve());
    };
    batch();
  });
}
