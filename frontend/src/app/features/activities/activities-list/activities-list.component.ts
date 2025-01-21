import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ActivitiesService } from '../activities.service';
import { Activity } from '../../../models/activity.model';
import { Observable } from 'rxjs';
import { SettingsService } from '../../settings/settings.service';
@Component({
  selector: 'app-activities-list',
  standalone: true,
  imports: [CommonModule, RouterModule],
  template: `
    <div class="activities-list">
      <h1>Activities</h1>
      @if (activities$ | async; as activities) {
        <div class="activities-container">
          @for (activity of activities; track activity.id) {
            <div class="activity-row" [routerLink]="['/activities', activity.id]">
              <div class="activity-main">
                <h3>{{ activity.name }}</h3>
                <div class="activity-meta">
                  <span class="sport-type">{{ activity.sport_type }}</span>
                  <span class="date">{{ activity.start_date | date:'medium' }}</span>
                </div>
              </div>
              <div class="activity-stats">
                <div class="stat">
                  <label>Distance</label>
                  <span>{{ this.activityDistance(activity) }}</span>
                </div>
                <div class="stat">
                  <label>Duration</label>
                  <span>{{ activity.duration / 60 | number:'1.0-0' }} min</span>
                </div>
                <div class="stat">
                  <label>Speed</label>
                  <span>{{ this.activitySpeed(activity) }}</span>
                </div>
                @if (activity.average_heartrate) {
                  <div class="stat">
                    <label>Heart Rate</label>
                    <span>{{ activity.average_heartrate | number:'1.0-0' }} bpm</span>
                  </div>
                }
              </div>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .activities-list {
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

    .activities-container {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }

    .activity-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 20px 24px;
      background: var(--bg-secondary);
      border-radius: 12px;
      box-shadow: 0 1px 3px var(--shadow-color);
      cursor: pointer;
      transition: all 0.2s ease;

      &:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px var(--hover-shadow);
      }
    }

    .activity-main {
      flex: 1;

      h3 {
        margin: 0;
        font-size: 1.125rem;
        font-weight: 500;
        color: var(--text-primary);
        letter-spacing: -0.01em;
      }
    }

    .activity-meta {
      display: flex;
      gap: 16px;
      margin-top: 6px;
      font-size: 0.875rem;
      color: var(--text-tertiary);
      font-weight: 400;

      .sport-type {
        text-transform: capitalize;
        color: var(--text-secondary);
      }

      .date {
        color: var(--text-tertiary);
      }
    }

    .activity-stats {
      display: flex;
      gap: 32px;
      margin-left: 24px;
    }

    .stat {
      display: flex;
      flex-direction: column;
      align-items: flex-end;
      min-width: 90px;

      label {
        font-size: 0.75rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-tertiary);
        margin-bottom: 2px;
      }

      span {
        font-size: 0.9375rem;
        color: var(--text-secondary);
        font-weight: 500;
        letter-spacing: -0.01em;
      }
    }
  `]
})
export class ActivitiesListComponent implements OnInit {
  activities$: Observable<Activity[]>;

  constructor(private activitiesService: ActivitiesService, private settingsService: SettingsService) {
    this.activities$ = this.activitiesService.getActivities();
  }

  ngOnInit(): void {}

  activityDistance(activity: Activity) {
    const units = this.settingsService.getUnits();
    let distance = units === 'metric' ? activity.distance : activity.distance * 0.621371;
    distance = Math.round(distance * 10) / 10;
    return `${distance} ${units === 'metric' ? 'km' : 'mi'}`;
  }

  activitySpeed(activity: Activity) {
    if (activity.sport_type.includes('running')) {
      return this.activityPace(activity);
    }

    const units = this.settingsService.getUnits();
    let speed = units === 'metric' ? activity.average_speed : activity.average_speed * 0.621371;
    speed = Math.round(speed * 10) / 10;
    return `${speed} ${units === 'metric' ? 'km/h' : 'mph'}`;
  }

  activityPace(activity: Activity) {
    // convert speed to pace (min:sec/mi or km)
    const units = this.settingsService.getUnits();
    let pace = units === 'metric' ? 60 / activity.average_speed : 60 / (activity.average_speed * 0.621371);
    pace = Math.round(pace * 10) / 10;
    const minutes = Math.floor(pace);
    const seconds = Math.round((pace - minutes) * 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}${units === 'metric' ? '/km' : '/mi'}`;
  }
}

