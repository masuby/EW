import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';

import { BulletinService } from '../../services/bulletin.service';
import { MapSelectorComponent, SpatialLevel } from '../../components/map-selector/map-selector.component';
import { PdfPreviewComponent } from '../../components/pdf-preview/pdf-preview.component';

type AlertTier = 'NO_WARNING' | 'ADVISORY' | 'WARNING' | 'MAJOR_WARNING';

@Component({
  selector: 'app-dmd',
  standalone: true,
  imports: [CommonModule, FormsModule, MapSelectorComponent, PdfPreviewComponent],
  template: `
    <div style="max-width: 980px; margin: 24px auto; padding: 0 16px;">
      <h2>DMD Multirisk Generator</h2>

      <div style="border:1px solid #e5e5e5; border-radius:8px; padding:16px; margin-top: 14px;">
        <div style="display:flex; gap:16px; flex-wrap:wrap;">
          <div style="flex:1; min-width: 220px;">
            <label>Bulletin number</label>
            <input type="number" [(ngModel)]="bulletinNumber" name="bulletinNumber" style="width:100%; padding:8px; margin-top:6px;" />
          </div>
          <div style="flex:1; min-width: 220px;">
            <label>Issue date</label>
            <input type="date" [(ngModel)]="issueDate" name="issueDate" style="width:100%; padding:8px; margin-top:6px;" />
          </div>
          <div style="flex:1; min-width: 180px;">
            <label>Issue time</label>
            <input type="time" [(ngModel)]="issueTime" name="issueTime" style="width:100%; padding:8px; margin-top:6px;" />
          </div>
          <div style="flex:1; min-width: 180px;">
            <label>Language</label>
            <select [(ngModel)]="language" name="language" style="width:100%; padding:8px; margin-top:6px;">
              <option value="sw">sw</option>
              <option value="en">en</option>
            </select>
          </div>
        </div>

        <hr style="margin:16px 0;" />

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:16px;">
          <div style="grid-column: 1 / -1;">
            <label>District alert tier</label>
            <select [(ngModel)]="tier" name="tier" style="width:100%; padding:8px; margin-top:6px;">
              <option *ngFor="let t of tiers" [value]="t">{{ t }}</option>
            </select>
          </div>
        </div>

        <div style="margin-top: 16px;" *ngIf="tier !== 'NO_WARNING'">
          <app-map-selector [level]="'districts'" (selectedChange)="selectedDistricts = $event"></app-map-selector>
        </div>

        <div style="margin-top: 16px; display:flex; gap:12px; align-items:center;">
          <button type="button" (click)="generate()" [disabled]="loading" style="padding:10px 16px;">
            {{ loading ? 'Generating...' : 'Generate DOCX/PDF' }}
          </button>
          <div *ngIf="error" style="color:#b00020;">{{ error }}</div>
        </div>
      </div>

      <div *ngIf="docxUrl || pdfUrl" style="margin-top:18px; border:1px solid #e5e5e5; border-radius:8px; padding:16px;">
        <div style="font-weight:700; margin-bottom:8px;">Generated Files</div>
        <div *ngIf="docxUrl"><a [href]="docxUrl" target="_blank" rel="noopener">Download DOCX</a></div>
        <div *ngIf="pdfUrl" style="margin-top:8px;"><a [href]="pdfUrl" target="_blank" rel="noopener">Download PDF</a></div>
        <div *ngIf="pdfUrl" style="margin-top: 12px;">
          <app-pdf-preview [pdfUrl]="pdfUrl"></app-pdf-preview>
        </div>
        <div *ngIf="!pdfUrl" style="color:#666; margin-top:8px;">PDF not available yet.</div>
      </div>
    </div>
  `,
})
export class DmdComponent {
  bulletinNumber = 1;
  issueDate = new Date().toISOString().slice(0, 10);
  issueTime = '08:00';
  language: 'sw' | 'en' = 'sw';

  tiers: AlertTier[] = ['NO_WARNING', 'ADVISORY', 'WARNING', 'MAJOR_WARNING'];
  tier: AlertTier = 'ADVISORY';
  selectedDistricts: string[] = [];

  loading = false;
  error: string | null = null;
  docxUrl: string | null = null;
  pdfUrl: string | null = null;

  constructor(private bulletin: BulletinService) {}

  generate() {
    this.loading = true;
    this.error = null;

    const selected = this.tier === 'NO_WARNING' ? [] : (this.selectedDistricts ?? []);

    const dayOffsets = [0, 1, 2];
    const tierForDay = dayOffsets.map((offset, idx) => {
      const dayNumber = idx + 1;
      const date = this.addDaysISO(this.issueDate, offset);

      return {
        day_number: dayNumber,
        date,
        recommendations: [],
        committee_note: '',
        // district tiers
        major_warning: this.tier === 'MAJOR_WARNING' ? selected : [],
        warning: this.tier === 'WARNING' ? selected : [],
        advisory: this.tier === 'ADVISORY' ? selected : [],
      };
    });

    const district_summaries = tierForDay.map((d) => ({
      day_number: d.day_number,
      major_warning: d.major_warning,
      warning: d.warning,
      advisory: d.advisory,
    }));

    const days = tierForDay.map((d) => ({
      day_number: d.day_number,
      date: d.date,
      recommendations: d.recommendations,
      committee_note: d.committee_note,
    }));

    const payload = {
      bulletin_number: this.bulletinNumber,
      issue_date: this.issueDate,
      issue_time: this.issueTime,
      language: this.language,
      district_summaries,
      days,
    };

    // Backend expects { payload: JsonNode }
    const request = { payload };

    this.bulletin.generateDmdMultirisk(request).subscribe({
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

  private addDaysISO(isoDate: string, days: number): string {
    const d = new Date(isoDate + 'T00:00:00');
    d.setDate(d.getDate() + days);
    return d.toISOString().slice(0, 10);
  }
}

