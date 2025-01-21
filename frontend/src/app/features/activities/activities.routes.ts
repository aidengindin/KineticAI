import { Routes } from '@angular/router';
import { ActivitiesListComponent } from './activities-list/activities-list.component';
import { ActivityDetailComponent } from './activity-detail/activity-detail.component';

export const ACTIVITIES_ROUTES: Routes = [
  {
    path: '',
    component: ActivitiesListComponent
  },
  {
    path: ':id',
    component: ActivityDetailComponent
  }
];
