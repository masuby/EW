import { Component, ElementRef, Input, OnChanges, SimpleChanges, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';

// pdfjs-dist doesn't ship perfect typings for all bundlers, so we use `any`.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
import * as pdfjsLib from 'pdfjs-dist';

@Component({
  selector: 'app-pdf-preview',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div style="margin-top: 14px; border:1px solid #e5e5e5; border-radius:8px; padding:12px;">
      <div style="font-weight:700; margin-bottom: 8px;">PDF Preview</div>
      <canvas #canvas style="width: 100%; height: auto; background:#fff; border-radius:6px;"></canvas>
    </div>
  `,
})
export class PdfPreviewComponent implements OnChanges {
  @Input({ required: true }) pdfUrl!: string;

  @ViewChild('canvas', { static: true }) canvasRef!: ElementRef<HTMLCanvasElement>;

  async ngOnChanges(changes: SimpleChanges) {
    const cur = changes['pdfUrl']?.currentValue;
    if (!cur) return;
    await this.render();
  }

  private async render() {
    const canvas = this.canvasRef.nativeElement;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    try {
      // Use CDN worker to avoid bundler issues.
      const ver: string | undefined = (pdfjsLib as any).version;
      if (ver) {
        pdfjsLib.GlobalWorkerOptions.workerSrc = `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${ver}/pdf.worker.min.js`;
      }

      // Load and render first page.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const loadingTask: any = (pdfjsLib as any).getDocument(this.pdfUrl);
      const pdf = await loadingTask.promise;
      const page = await pdf.getPage(1);

      const viewport = page.getViewport({ scale: 1.25 });
      canvas.width = viewport.width;
      canvas.height = viewport.height;

      await page.render({ canvasContext: ctx, viewport }).promise;
    } catch {
      // Fail silently; preview is optional.
    }
  }
}

