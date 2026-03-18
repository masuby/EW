import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { API_URLS } from '../config/api';

@Injectable({ providedIn: 'root' })
export class BulletinService {
  constructor(private http: HttpClient) {}

  generateTma722e4(payload: unknown): Observable<any> {
    return this.http.post(API_URLS.tma722e4Generate, payload);
  }

  generateDmdMultirisk(payload: unknown): Observable<any> {
    return this.http.post(API_URLS.dmdMultiriskGenerate, payload);
  }
}

