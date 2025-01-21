import { CommonModule } from "@angular/common";
import { Component } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { SettingsService } from "./settings.service";

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="settings-container">
      <h1>Settings</h1>
      <div class="settings-card">
        <h2>General</h2>
        <div class="settings-item">
          <label for="units">Units</label>
          <select id="units" [(ngModel)]="selectedUnits" (ngModelChange)="onUnitsChange($event)">
            <option value="metric">Metric</option>
            <option value="imperial">Imperial</option>
          </select>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .settings-container {
      padding: 20px;
      max-width: 1200px;
      margin: 0 auto;

      h1 {
        font-size: 2rem;
        font-weight: 600;
        color: var(--text-primary);
        margin-bottom: 1.5rem;
      }
    }

    .settings-card {
      background: var(--bg-secondary);
      border-radius: 12px;
      box-shadow: 0 1px 3px var(--shadow-color);
      padding: 24px;

      h2 {
        font-size: 1.25rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0 0 1.5rem;
      }
    }

    .settings-item {
      display: flex;
      align-items: center;
      gap: 16px;
      padding: 12px 0;

      label {
        font-size: 0.875rem;
        font-weight: 500;
        color: var(--text-secondary);
        min-width: 120px;
      }

      select {
        background: var(--bg-primary);
        border: 1px solid var(--border-color);
        border-radius: 6px;
        padding: 8px 12px;
        font-size: 0.875rem;
        color: var(--text-primary);
        min-width: 160px;
        cursor: pointer;
        transition: all 0.2s ease;

        &:hover {
          border-color: var(--text-tertiary);
        }

        &:focus {
          outline: none;
          border-color: var(--text-secondary);
          box-shadow: 0 0 0 2px var(--border-color);
        }

        option {
          background: var(--bg-secondary);
          color: var(--text-primary);
        }
      }
    }
  `]
})
export class SettingsComponent {
  selectedUnits: string;

  constructor(private settingsService: SettingsService) {
    this.selectedUnits = this.settingsService.getUnits();
  }

  onUnitsChange(units: string) {
    this.settingsService.setUnits(units);
  }
}
