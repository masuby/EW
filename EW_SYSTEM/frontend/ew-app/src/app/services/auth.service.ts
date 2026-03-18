import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable, tap } from 'rxjs';

import { API_URLS } from '../config/api';

export interface LoginResponse {
  token: string;
  role: string;
  displayName: string;
}

export interface MeResponse {
  username: string;
  role: string;
  displayName: string | null;
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly tokenKey = 'ew_token';

  constructor(private http: HttpClient) {}

  getToken(): string | null {
    return localStorage.getItem(this.tokenKey);
  }

  login(username: string, password: string): Observable<LoginResponse> {
    return this.http
      .post<LoginResponse>(API_URLS.login, { username, password })
      .pipe(
        tap((res) => {
          localStorage.setItem(this.tokenKey, res.token);
        })
      );
  }

  me(): Observable<MeResponse> {
    return this.http.get<MeResponse>(API_URLS.me);
  }

  logout(): void {
    localStorage.removeItem(this.tokenKey);
  }
}

