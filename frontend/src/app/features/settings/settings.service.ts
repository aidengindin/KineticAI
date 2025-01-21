import { Injectable } from "@angular/core";

@Injectable({
  providedIn: 'root'
})
export class SettingsService {
  private units: string = 'metric';

  constructor() {
  }

  getUnits() {
    return this.units;
  }

  setUnits(units: string) {
    this.units = units;
  }

}
