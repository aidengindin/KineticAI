from typing import Tuple


def predict(
        distance: int,
        cp: int,
        tte: int,
        running_effectiveness: float,
        riegel_exponent: float,
        athlete_weight: float,
        num_iterations: int = 10,
) -> Tuple[int, int]:
    unnormalized_re = running_effectiveness / athlete_weight

    def power_for_duration(duration: int) -> int:
        if duration < tte:
            raise NotImplementedError("Can't yet predict power for duration less than TTE")
        if duration == tte:
            return cp
        return cp * (duration / tte) ** riegel_exponent

    def time_for_power(power: int) -> int:
        speed = power * unnormalized_re
        return distance / speed

    # Start with initial guess of 90% of CP
    power = cp * 0.9

    for _ in range(num_iterations):
        predicted_time = time_for_power(power)
        sustainable_power = power_for_duration(predicted_time)
        power = sustainable_power

    return predicted_time, power
