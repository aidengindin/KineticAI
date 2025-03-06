import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: 'activities',
    loadChildren: () => import('./features/activities/activities.routes')
      .then(m => m.ACTIVITIES_ROUTES)
  },
  {
    path: '',
    redirectTo: 'activities',
    pathMatch: 'full'
  },
  {
    path: 'racePrediction',
    loadChildren: () => import('./features/racePrediction/racePrediction.routes')
      .then
      (m => m.RACE_PREDICTION_ROUTES)
  },
  {
    path: 'settings',
    loadChildren: () => import('./features/settings/settings.routes')
      .then(m => m.SETTINGS_ROUTES)
  }
];
