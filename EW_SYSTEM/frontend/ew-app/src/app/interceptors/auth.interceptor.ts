import { Injectable } from '@angular/core';
import {
  HttpEvent,
  HttpHandler,
  HttpInterceptor,
  HttpRequest,
} from '@angular/common/http';
import { Observable, catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';
import { HTTP_INTERCEPTORS } from '@angular/common/http';

@Injectable()
export class AuthInterceptor implements HttpInterceptor {
  constructor(private auth: AuthService) {}

  intercept(req: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    const token = this.auth.getToken();
    // Never attach an Authorization header to the login request; a stale/invalid token
    // would otherwise cause the backend JWT filter to reject the request before login runs.
    const isLogin = req.url.endsWith('/api/auth/login');
    if (!token || isLogin) return next.handle(req);

    const authReq = req.clone({
      setHeaders: {
        Authorization: `Bearer ${token}`,
      },
    });
    return next.handle(authReq).pipe(
      catchError((err: any) => {
        // If a token is invalid/expired, clear it so the user can log in again.
        // Don't hard-redirect here; let the UI show the actual error first.
        if (err?.status === 401) {
          this.auth.logout();
        }
        return throwError(() => err);
      }),
    );
  }
}

export const AUTH_INTERCEPTOR_PROVIDER = {
  provide: HTTP_INTERCEPTORS,
  useClass: AuthInterceptor,
  multi: true,
};

