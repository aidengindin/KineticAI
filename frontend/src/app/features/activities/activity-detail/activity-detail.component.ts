import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { Observable, switchMap } from 'rxjs';
import { ActivitiesService } from '../activities.service';
import { Activity } from '../../../models/activity.model';

@Component({
  selector: 'app-activity-detail',
  standalone: true,
  imports: [CommonModule],
  template: `
    <div class="activity-detail">
      @if (activity$ | async; as activity) {
        <h1>{{ activity.name }}</h1>
        <div class="activity-info">
          <div class="info-item">
            <label>Sport</label>
            <span>{{ activity.sport_type }}</span>
          </div>
          <div class="info-item">
            <label>Date</label>
            <span>{{ activity.start_date | date:'medium' }}</span>
          </div>
          <div class="info-item">
            <label>Distance</label>
            <span>{{ activity.distance | number:'1.1-1' }} km</span>
          </div>
          <div class="info-item">
            <label>Duration</label>
            <span>{{ activity.duration | number:'1.0-0' }} seconds</span>
          </div>
          <div class="info-item">
            <label>Average Speed</label>
            <span>{{ activity.average_speed | number:'1.1-1' }} km/h</span>
          </div>
          @if (activity.average_heartrate) {
            <div class="info-item">
              <label>Average Heart Rate</label>
              <span>{{ activity.average_heartrate | number:'1.0-0' }} bpm</span>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .activity-detail {
      padding: 20px;
      background: var(--bg-secondary);
      border-radius: 12px;
      box-shadow: 0 1px 3px var(--shadow-color);
      max-width: 1200px;
      margin: 20px auto;
    }

    h1 {
      margin: 0 0 20px;
      font-size: 2rem;
      color: var(--text-primary);
    }

    .activity-info {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 20px;
    }

    .info-item {
      display: flex;
      flex-direction: column;
      gap: 5px;

      label {
        font-size: 0.875rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--text-tertiary);
      }

      span {
        font-size: 1.1rem;
        color: var(--text-secondary);
        font-weight: 500;
      }
    }
  `]
})
export class ActivityDetailComponent implements OnInit {
  activity$: Observable<Activity>;

  constructor(
    private route: ActivatedRoute,
    private activitiesService: ActivitiesService
  ) {
    this.activity$ = this.route.params.pipe(
      switchMap(params => this.activitiesService.getActivity(params['id']))
    );
  }

  ngOnInit(): void {}
}
