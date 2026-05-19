# temperature_system.py - Deterministic temperature simulation
#
# Formula: seasonal_base + diurnal + weather_mod + slow_noise + day_noise + slot_noise
#   seasonal_base: cosine wave, trough at day 0 (winter), peak at day 182 (summer)
#   diurnal:       cosine wave, peak at 14:00, trough at 02:00
#   weather_mod:   per-weather adjustment (clouds/precip cool things down)
#   slow_noise:    seeded week-level variation (+/-3 C) for warm/cold spells
#   day_noise:     seeded day-level variation (+/-2 C)
#   slot_noise:    seeded 3h-slot variation (+/-1 C)
# Final value is clamped to [-5, 35] C.

import math

_SEASONAL_MEAN = 13.0   # midpoint of the seasonal swing (C)
_SEASONAL_AMP  = 13.0   # half-range of the seasonal swing (C)
# => trough  0 C at d=0, peak 26 C at d=182

_DIURNAL_AMP = 5.0      # +/- C around the daily mean

_WEATHER_MOD = {
    "Clear":    2.0,
    "Cloudy":  -0.5,
    "Overcast": -1.5,
    "Windy":   -1.0,
    "Rain":    -3.0,
    "Storm":   -4.0,
    "Snow":    -5.0,
}

_SLOW_NOISE_AMP = 3.0   # week-level warm/cold spells
_DAY_NOISE_AMP  = 2.0   # day-to-day variation
_SLOT_NOISE_AMP = 1.0   # within-day slot variation

_MIN_TEMP = -5.0
_MAX_TEMP = 35.0


def _xorshift32(x):
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= (x >> 17)
    x ^= (x << 5) & 0xFFFFFFFF
    return x & 0xFFFFFFFF


def _noise(seed, amplitude):
    """Return a signed float in [-amplitude, +amplitude] from a 32-bit seed."""
    v = _xorshift32((seed * 2654435761 + 1) & 0xFFFFFFFF)
    return (v % 10001) / 10000.0 * 2.0 * amplitude - amplitude


def get_temperature(day_number, season_offset, hour, weather, pet_seed):
    """Return the current temperature in Celsius.

    Deterministic for a given (day_number, season_offset, hour, weather, pet_seed).
    day_number    : absolute game day (0 = game start)
    season_offset : shifts where in the year day 0 falls (stored in environment)
    hour          : 0-23 game hour
    weather       : current weather string
    pet_seed      : unique per-pet seed for noise variation
    """
    d = (day_number + season_offset) % 365

    # Seasonal base: coldest at d=0, warmest at d=182
    seasonal = _SEASONAL_MEAN - _SEASONAL_AMP * math.cos(2.0 * math.pi * d / 365.0)

    # Diurnal: peak at 14:00, trough at 02:00
    diurnal = _DIURNAL_AMP * math.cos(2.0 * math.pi * (hour - 14.0) / 24.0)

    weather_mod = _WEATHER_MOD.get(weather, 0.0)

    # Seeded noise layered at week, day, and 3h-slot granularity
    week = day_number // 7
    slow_seed = (pet_seed ^ (week * 1234567891)) & 0xFFFFFFFF
    slow = _noise(slow_seed, _SLOW_NOISE_AMP)

    day_seed = (pet_seed ^ (day_number * 2654435761)) & 0xFFFFFFFF
    day_noise = _noise(day_seed, _DAY_NOISE_AMP)

    slot = hour // 3
    slot_seed = (day_seed ^ (slot * 1234567)) & 0xFFFFFFFF
    slot_noise = _noise(slot_seed, _SLOT_NOISE_AMP)

    temp = seasonal + diurnal + weather_mod + slow + day_noise + slot_noise
    if temp < _MIN_TEMP:
        return _MIN_TEMP
    if temp > _MAX_TEMP:
        return _MAX_TEMP
    return temp
