import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="app-container">
      <header class="app-header">
        <h1>Kinetic</h1>
        <nav>
          <a routerLink="/activities" routerLinkActive="active">Activities</a>
          <a routerLink="/settings" routerLinkActive="active">Settings</a>
        </nav>
      </header>
      <main class="app-content">
        <router-outlet></router-outlet>
      </main>
    </div>
  `,
  styles: [`
    .app-container {
      min-height: 100vh;
      background-color: var(--bg-primary);
      color: var(--text-primary);
    }

    .app-header {
      background-color: var(--bg-secondary);
      border-bottom: 1px solid var(--border-color);
      padding: 1rem 2rem;
      display: flex;
      justify-content: space-between;
      align-items: center;
      box-shadow: 0 1px 3px var(--shadow-color);

      h1 {
        font-size: 1.5rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
      }

      nav {
        a {
          color: var(--text-secondary);
          text-decoration: none;
          font-weight: 500;
          padding: 0.5rem 1rem;
          border-radius: 6px;
          transition: all 0.2s ease;

          &:hover {
            color: var(--text-primary);
            background-color: var(--bg-primary);
          }

          &.active {
            color: var(--text-primary);
            background-color: var(--bg-primary);
          }
        }
      }
    }

    .app-content {
      min-height: calc(100vh - 4rem);
      background-color: var(--bg-primary);
    }
  `]
})
export class AppComponent {
  title = 'KineticAI';
}
