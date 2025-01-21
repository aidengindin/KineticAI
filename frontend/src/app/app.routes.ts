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
    path: 'settings',
    loadChildren: () => import('./features/settings/settings.routes')
      .then(m => m.SETTINGS_ROUTES)
  }
];
