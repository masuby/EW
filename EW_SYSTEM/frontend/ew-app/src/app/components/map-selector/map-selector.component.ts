import { AfterViewInit, Component, ElementRef, EventEmitter, Input, Output, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';

import * as L from 'leaflet';

import { API_URLS } from '../../config/api';

export type SpatialLevel = 'regions' | 'districts';

@Component({
  selector: 'app-map-selector',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div style="border: 1px solid #e5e5e5; border-radius: 8px; padding: 12px;">
      <div style="display:flex; justify-content:space-between; align-items:center; gap:12px;">
        <div>
          <div style="font-weight:600;">Map selector ({{ level }})</div>
          <div style="color:#666; font-size: 12px; margin-top: 4px;">
            Click to add polygon vertices, then press <b>Finish</b>.
          </div>
        </div>
        <div style="display:flex; gap:8px;">
          <button type="button" (click)="clear()" [disabled]="loading" style="padding:8px 10px;">Clear</button>
          <button type="button" (click)="finish()" [disabled]="loading" style="padding:8px 10px;">Finish</button>
        </div>
      </div>

      <div #mapHost style="height: 420px; margin-top: 12px; border-radius: 6px; overflow:hidden;"></div>

      <div *ngIf="selected.length" style="margin-top: 12px;">
        <div style="font-weight:600; margin-bottom: 8px;">Selected:</div>
        <div style="max-height: 140px; overflow:auto; font-size: 13px;">
          <div *ngFor="let s of selected">{{ s }}</div>
        </div>
      </div>
    </div>
  `,
})
export class MapSelectorComponent implements AfterViewInit {
  @Input({ required: true }) level: SpatialLevel = 'regions';
  @Output() selectedChange = new EventEmitter<string[]>();

  @ViewChild('mapHost', { static: true }) mapHost!: ElementRef<HTMLDivElement>;

  private map!: L.Map;
  private polygon: L.Polygon | null = null;
  private points: L.LatLng[] = [];

  selected: string[] = [];
  loading = false;

  constructor(private http: HttpClient) {}

  ngAfterViewInit(): void {
    this.map = L.map(this.mapHost.nativeElement).setView([-6.5, 39.2], 6);

    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(this.map);

    this.map.on('click', (e) => {
      this.points.push(e.latlng);
      this.redrawTempPolygon();
    });
  }

  clear(): void {
    this.points = [];
    if (this.polygon) this.polygon.remove();
    this.polygon = null;
    this.selected = [];
    this.selectedChange.emit([]);
  }

  private redrawTempPolygon(): void {
    if (this.polygon) this.polygon.remove();
    if (this.points.length < 2) return;

    // Leaflet draws a polygon; it will close automatically.
    this.polygon = L.polygon(this.points, { color: '#d00000', weight: 2, fillOpacity: 0.2 }).addTo(this.map);
  }

  finish(): void {
    if (this.points.length < 3) return;
    this.loading = true;

    const ring = [
      ...this.points.map((p) => [p.lng, p.lat] as [number, number]),
    ];
    // close ring
    const first = ring[0];
    ring.push([first[0], first[1]]);

    const geometry = {
      type: 'Polygon',
      coordinates: [ring],
    };

    const body = { level: this.level, geometry };

    this.http.post<any>(API_URLS.spatialIntersections, body).subscribe({
      next: (res) => {
        this.selected = res?.selected ?? [];
        this.selectedChange.emit(this.selected);
        this.loading = false;
      },
      error: () => {
        this.loading = false;
      },
    });
  }
}

