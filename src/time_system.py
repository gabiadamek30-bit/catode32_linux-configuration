"""time_system.py - Simulated in-game time and calendar management."""

_MOON_PHASES = (
    "New", "Wax Cres", "1st Qtr", "Wax Gib",
    "Full", "Wan Gib", "3rd Qtr", "Wan Cres",
)

# Season day boundaries (applied to (day_number + season_offset) % 365).
# Winter wraps around 0: days 0-59 and 356-364.
# Spring:  60-151  (92 days)
# Summer: 152-264 (113 days)
# Fall:   265-355  (91 days)
# Winter: 356-364 +  0-59  (69 days)
def get_season(day_number, offset=0):
    """Return the season name for the given game day and offset."""
    d = (day_number + offset) % 365
    if d < 60:
        return "Winter"
    if d < 152:
        return "Spring"
    if d < 265:
        return "Summer"
    if d < 356:
        return "Fall"
    return "Winter"


class TimeSystem:
    """Advances simulated in-game time and keeps the moon phase, season, and
    temperature current."""

    def __init__(self, game_minutes_per_second=1.0):
        self._accumulator = 0.0
        self.game_minutes_per_second = game_minutes_per_second
        self.pet_seed = 0        # set by Game after context is loaded
        self._last_temp_hour = -1

    def advance(self, dt, environment, weather_system=None):
        """Advance time by dt real seconds. Calls weather_system.update if provided."""
        self._accumulator += dt * self.game_minutes_per_second
        if self._accumulator < 1.0:
            return

        mins = int(self._accumulator)
        self._accumulator -= mins

        total_minutes = environment.get('time_minutes', 0) + mins
        old_hours = environment.get('time_hours', 12)
        new_hours_raw = old_hours + total_minutes // 60
        environment['time_hours'] = new_hours_raw % 24
        environment['time_minutes'] = total_minutes % 60

        if new_hours_raw >= 24:
            environment['day_number'] = environment.get('day_number', 0) + (new_hours_raw // 24)
            self.update_moon_phase(environment)
            self.update_season(environment)

        # Update temperature whenever the displayed hour changes
        current_hour = environment.get('time_hours', 12)
        if current_hour != self._last_temp_hour:
            self._last_temp_hour = current_hour
            self.update_temperature(environment)

        if weather_system:
            weather_system.update(mins, environment)

    def update_moon_phase(self, environment):
        """Recompute and store the current moon phase in the environment dict."""
        day = environment.get('day_number', 0)
        environment['moon_phase'] = _MOON_PHASES[(day // 6 + 2) % 8]

    def update_season(self, environment):
        """Recompute and store the current season in the environment dict."""
        day = environment.get('day_number', 0)
        offset = environment.get('season_offset', 0)
        environment['season'] = get_season(day, offset)

    def update_temperature(self, environment):
        """Recompute and store the current temperature (C) in the environment dict."""
        from temperature_system import get_temperature
        day = environment.get('day_number', 0)
        offset = environment.get('season_offset', 0)
        hour = environment.get('time_hours', 12)
        weather = environment.get('weather', 'Clear')
        environment['temperature'] = get_temperature(day, offset, hour, weather, self.pet_seed)
