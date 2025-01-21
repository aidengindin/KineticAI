export interface Activity {
  id: string;
  user_id: string;
  start_date: string;
  name: string;
  sport_type: string;
  duration: number;
  distance: number;
  average_speed: number;
  average_heartrate?: number;
  gear_id?: string;
}
