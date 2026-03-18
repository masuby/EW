import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { BulletinService } from '../../services/bulletin.service';
import { MapSelectorComponent, SpatialLevel } from '../../components/map-selector/map-selector.component';
import { PdfPreviewComponent } from '../../components/pdf-preview/pdf-preview.component';

type AlertLevel = 'NO_WARNING' | 'ADVISORY' | 'WARNING' | 'MAJOR_WARNING';
type HazardType = 'HEAVY_RAIN' | 'STRONG_WIND' | 'LARGE_WAVES' | 'FLOODS' | 'LANDSLIDES' | 'EXTREME_TEMPERATURE';

@Component({
  selector: 'app-tma',
  standalone: true,
  imports: [CommonModule, FormsModule, MapSelectorComponent, PdfPreviewComponent],
  template: `
    <div style="max-width: 980px; margin: 24px auto; padding: 0 16px;">
      <h2>TMA 722E_4 Generator</h2>

      <div style="border:1px solid #e5e5e5; border-radius:8px; padding:16px; margin-top:14px;">
        <div style="display:flex; gap:16px; flex-wrap:wrap;">
          <div style="flex:1; min-width: 200px;">
            <label>Issue date</label>
            <input type="date" [(ngModel)]="issueDate" name="issueDate" style="width:100%; padding:8px; margin-top:6px;" />
          </div>
          <div style="flex:1; min-width: 160px;">
            <label>Issue time</label>
            <input type="time" [(ngModel)]="issueTime" name="issueTime" style="width:100%; padding:8px; margin-top:6px;" />
          </div>
        </div>

        <hr style="margin:16px 0;" />

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
          <div>
            <label>Hazard type</label>
            <select [(ngModel)]="hazard.type" name="hazardType" style="width:100%; padding:8px; margin-top:6px;">
              <option *ngFor="let t of hazardTypes" [value]="t">{{ t }}</option>
            </select>
          </div>
          <div>
            <label>Alert level</label>
            <select [(ngModel)]="hazard.alert_level" name="alertLevel" style="width:100%; padding:8px; margin-top:6px;">
              <option *ngFor="let a of alertLevels" [value]="a">{{ a }}</option>
            </select>
          </div>

          <div style="grid-column: 1 / -1;">
            <label>Description</label>
            <textarea [(ngModel)]="hazard.description" name="hazardDescription" rows="3" style="width:100%; padding:8px; margin-top:6px;"></textarea>
          </div>

          <div style="grid-column: 1 / -1;">
            <label>Impacts expected</label>
            <textarea [(ngModel)]="hazard.impacts_expected" name="impactsExpected" rows="3" style="width:100%; padding:8px; margin-top:6px;"></textarea>
          </div>
        </div>

        <div style="margin-top: 16px;" *ngIf="hazard.alert_level !== 'NO_WARNING'">
          <app-map-selector [level]="level" (selectedChange)="hazard.regions = $event"></app-map-selector>
        </div>

        <div style="margin-top: 16px; display:flex; gap:12px; align-items:center;">
          <button type="button" (click)="generate()" [disabled]="loading" style="padding:10px 16px;">
            {{ loading ? 'Generating...' : 'Generate DOCX/PDF' }}
          </button>
          <div *ngIf="error" style="color:#b00020;">{{ error }}</div>
        </div>
      </div>

      <div *ngIf="docxUrl || pdfUrl" style="margin-top: 18px; border:1px solid #e5e5e5; border-radius:8px; padding:16px;">
        <div style="font-weight:700; margin-bottom:8px;">Generated Files</div>
        <div *ngIf="docxUrl">
          <a [href]="docxUrl" target="_blank" rel="noopener">Download DOCX</a>
        </div>
        <div *ngIf="pdfUrl">
          <a [href]="pdfUrl" target="_blank" rel="noopener">Download PDF</a>
        </div>
        <div *ngIf="pdfUrl" style="margin-top: 12px;">
          <app-pdf-preview [pdfUrl]="pdfUrl"></app-pdf-preview>
        </div>
        <div *ngIf="!pdfUrl" style="color:#666; margin-top:8px;">PDF not available yet (soffice conversion failed/missing).</div>
      </div>
    </div>
  `,
})
export class TmaComponent {
  issueDate = new Date().toISOString().slice(0, 10);
  issueTime = '08:00';

  alertLevels: AlertLevel[] = ['NO_WARNING', 'ADVISORY', 'WARNING', 'MAJOR_WARNING'];
  hazardTypes: HazardType[] = ['HEAVY_RAIN', 'STRONG_WIND', 'LARGE_WAVES', 'FLOODS', 'LANDSLIDES', 'EXTREME_TEMPERATURE'];

  level: SpatialLevel = 'regions';
  selectedRegions: string[] = [];

  hazard: {
    type: HazardType;
    alert_level: AlertLevel;
    description: string;
    impacts_expected: string;
    likelihood?: string;
    impact?: string;
    regions: string[];
  } = {
    type: 'HEAVY_RAIN',
    alert_level: 'ADVISORY',
    description: '',
    impacts_expected: '',
    likelihood: 'MEDIUM',
    impact: 'HIGH',
    regions: [],
  };

  loading = false;
  error: string | null = null;

  docxUrl: string | null = null;
  pdfUrl: string | null = null;

  constructor(private bulletin: BulletinService) {}

  // MapSelector emits selectedChange; we capture it by binding to selectedChange
  // (the MapSelector itself is currently rendered without outputs binding in template).
  // For now we update selection manually after the user finishes.

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  generate() {
    this.loading = true;
    this.error = null;

    const hazardList = this.hazard.alert_level === 'NO_WARNING'
      ? []
      : [{
        type: this.hazard.type,
        alert_level: this.hazard.alert_level,
        description: this.hazard.description ?? '',
        impacts_expected: this.hazard.impacts_expected ?? '',
        likelihood: this.hazard.likelihood,
        impact: this.hazard.impact,
        regions: this.hazard.regions ?? [],
      }];

    const issue = new Date(this.issueDate + 'T00:00:00');
    const days = Array.from({ length: 5 }).map((_, idx) => {
      const d = new Date(issue);
      d.setDate(d.getDate() + idx);
      const iso = d.toISOString().slice(0, 10);
      return {
        date: iso,
        hazards: hazardList.map((h) => ({ ...h, regions: this.hazard.regions })),
      };
    });

    const payload = {
      issue_date: this.issueDate,
      issue_time: this.issueTime,
      days,
    };

    // Backend expects { payload: JsonNode }
    const request = { payload };

    this.bulletin.generateTma722e4(request).subscribe({
      next: (res: any) => {
        this.loading = false;
        this.docxUrl = res?.docxUrl ?? res?.files?.docx ?? null;
        this.pdfUrl = res?.pdfUrl ?? res?.files?.pdf ?? null;
      },
      error: (err: any) => {
        this.loading = false;
        this.error = err?.error?.error ?? err?.message ?? 'Generation failed';
      },
    });
  }
}

