from typing import Tuple
import numpy as np
from scipy.optimize import curve_fit

from performance_modeling.db.power_curve import PowerCurveRepository

def morton_model(t, cp, wp, k):
    return cp + wp / (t - k)

def fit_params(time_power_dict):
    times = np.array(sorted(time_power_dict.keys()))
    powers = np.array([time_power_dict[t] for t in times])

    short_mask = times < 180
    medium_mask = (times >= 180) & (times < 720)
    long_mask = times >= 720

    best_fit = {
        'cp': None,
        'wp': None,
        'k': None,
        'error': float('inf')
    }

    for short_t in times[short_mask]:
        for medium_t in times[medium_mask]:
            for long_t in times[long_mask]:
                t_subset = np.array([short_t, medium_t, long_t])
                p_subset = np.array([time_power_dict[t] for t in t_subset])

                try:
                    popt, _ = curve_fit(
                        morton_model,
                        t_subset,
                        p_subset,
                        bounds=([100, 5000, -120], [400, 50000, 120]),
                        p0=[250, 25000, 0]
                    )

                    cp, wp, k = popt

                    predicted = morton_model(times, cp, wp, k)
                    error = np.mean((predicted - powers) ** 2)

                    if error < best_fit['error']:
                        best_fit = {
                            'cp': cp,
                            'wp': wp,
                            'k': k,
                            'error': error
                        }

                except RuntimeError:
                    continue  # Skip if curve_fit fails to converge

    if best_fit['cp'] is None:
        raise ValueError('Failed to find valid fit')

    return best_fit

async def estimate_cp_wp(
        repository: PowerCurveRepository,
        user_id: str,
        sport: str
) -> Tuple[float, float]:
    power_curves = await repository.get_user_power_curve(user_id, sport)
    time_power_dict = {power_curve.time: power_curve.power for power_curve in power_curves}

    return fit_params(time_power_dict)
