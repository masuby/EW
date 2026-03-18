import { Routes } from '@angular/router';

import { LoginComponent } from './pages/login/login.component';
import { TmaComponent } from './pages/tma/tma.component';
import { DmdComponent } from './pages/dmd/dmd.component';
import { authGuard } from './guards/auth.guard';

export const routes: Routes = [
  { path: '', redirectTo: '/tma', pathMatch: 'full' },
  { path: 'login', component: LoginComponent },
  { path: 'tma', component: TmaComponent, canActivate: [authGuard] },
  { path: 'dmd', component: DmdComponent, canActivate: [authGuard] },
  { path: '**', redirectTo: '/tma' },
];
