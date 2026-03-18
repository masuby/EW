import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';

import { AuthService } from '../../services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div style="max-width: 520px; margin: 40px auto; padding: 16px; border: 1px solid #e5e5e5; border-radius: 8px;">
      <h2 style="margin-top:0;">EW System Login</h2>
      <form (ngSubmit)="submit()">
        <div style="margin-bottom: 12px;">
          <label>Username</label>
          <input class="input" [(ngModel)]="username" name="username" style="width:100%; padding:8px; margin-top:6px;" />
        </div>
        <div style="margin-bottom: 12px;">
          <label>Password</label>
          <input class="input" [(ngModel)]="password" name="password" type="password" style="width:100%; padding:8px; margin-top:6px;" />
        </div>

        <div *ngIf="error" style="color:#b00020; margin-bottom: 12px;">
          {{ error }}
        </div>

        <button type="submit" [disabled]="loading" style="padding:10px 16px;">
          {{ loading ? 'Signing in...' : 'Sign in' }}
        </button>
      </form>
    </div>
  `,
})
export class LoginComponent {
  username = '';
  password = '';
  loading = false;
  error: string | null = null;

  constructor(private auth: AuthService, private router: Router) {}

  submit() {
    this.error = null;
    // Clear stale tokens so the interceptor can't attach an invalid JWT.
    this.auth.logout();
    this.loading = true;
    this.auth.login(this.username, this.password).subscribe({
      next: () => {
        this.loading = false;
        this.router.navigate(['/tma']);
      },
      error: (err) => {
        this.loading = false;
        this.error = err?.error?.error ?? 'Login failed';
      },
    });
  }
}

