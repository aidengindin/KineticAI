import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, of } from 'rxjs';
import { Activity } from '../../models/activity.model';
import { environment } from '../../../environments/environment';

const MOCK_ACTIVITIES: Activity[] = [
  {
    id: '1',
    user_id: 'user123',
    name: 'Morning Run',
    sport_type: 'running',
    start_date: new Date(2024, 0, 21, 8, 30).toISOString(),
    duration: 3600,
    distance: 10.5,
    average_speed: 10.5,
    average_heartrate: 155
  },
  {
    id: '2',
    user_id: 'user123',
    name: 'Evening Ride',
    sport_type: 'cycling',
    start_date: new Date(2024, 0, 20, 18, 0).toISOString(),
    duration: 5400,
    distance: 30.2,
    average_speed: 20.1,
    average_heartrate: 145
  },
  {
    id: '3',
    user_id: 'user123',
    name: 'Trail Run',
    sport_type: 'trail_running',
    start_date: new Date(2024, 0, 19, 10, 0).toISOString(),
    duration: 4500,
    distance: 12.3,
    average_speed: 9.8,
    average_heartrate: 162
  },
  {
    id: '4',
    user_id: 'user123',
    name: 'Long Ride',
    sport_type: 'cycling',
    start_date: new Date(2024, 0, 18, 9, 0).toISOString(),
    duration: 10800,
    distance: 80.5,
    average_speed: 26.8,
    average_heartrate: 148,
    gear_id: 'bike1'
  },
  {
    id: '5',
    user_id: 'user123',
    name: 'Recovery Run',
    sport_type: 'running',
    start_date: new Date(2024, 0, 17, 7, 30).toISOString(),
    duration: 2700,
    distance: 6.2,
    average_speed: 8.3,
    average_heartrate: 138
  }
];

@Injectable({
  providedIn: 'root'
})
export class ActivitiesService {
  private apiUrl = `${environment.apiUrl}/activities`;
  private useMockData = true; // Toggle this to switch between mock and real data

  constructor(private http: HttpClient) {}

  getActivities(params: {
    user_id?: string;
    start_date?: string;
    end_date?: string;
    sport_type?: string;
    limit?: number;
    offset?: number;
  } = {}): Observable<Activity[]> {
    if (this.useMockData) {
      let filteredActivities = [...MOCK_ACTIVITIES];

      if (params.sport_type) {
        filteredActivities = filteredActivities.filter(a => a.sport_type === params.sport_type);
      }
      if (params.limit) {
        filteredActivities = filteredActivities.slice(params.offset || 0, (params.offset || 0) + params.limit);
      }

      return of(filteredActivities);
    }

    return this.http.get<Activity[]>(this.apiUrl, { params });
  }

  getActivity(id: string): Observable<Activity> {
    if (this.useMockData) {
      const activity = MOCK_ACTIVITIES.find(a => a.id === id);
      return of(activity!);
    }

    return this.http.get<Activity>(`${this.apiUrl}/${id}`);
  }

  getActivityLaps(id: string) {
    if (this.useMockData) {
      return of([]);
    }

    return this.http.get(`${this.apiUrl}/${id}/laps`);
  }

  getActivityStreams(id: string, fields?: string[]) {
    if (this.useMockData) {
      return of([]);
    }

    const params = fields ? new HttpParams().set('fields', fields.join(',')) : {};
    return this.http.get(`${this.apiUrl}/${id}/streams`, { params });
  }
}
