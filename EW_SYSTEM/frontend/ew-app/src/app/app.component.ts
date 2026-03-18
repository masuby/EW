import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet],
  // Keep the root minimal so routed pages always render (no starter placeholder).
  template: '<router-outlet />',
})
export class AppComponent {
  title = 'ew-app';
}
