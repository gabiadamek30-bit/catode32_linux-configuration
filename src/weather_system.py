# weather_system.py - Deterministic weather progression via seeded Markov chain


def _xorshift32(x):
    """Simple xorshift PRNG for deterministic pseudo-random values"""
    x ^= (x << 13) & 0xFFFFFFFF
    x ^= (x >> 17)
    x ^= (x << 5) & 0xFFFFFFFF
    return x & 0xFFFFFFFF


def _seeded_rand(step):
    """Mix step into a well-distributed seed, then xorshift."""
    x = (step * 2654435761 + 1) & 0xFFFFFFFF
    return _xorshift32(x)


# Markov chain: each state lists its possible successors (including itself).
# Order matters for the weighted pick — all options are equally likely.
_TRANSITIONS = {
    "Clear":    ("Clear", "Cloudy", "Windy"),
    "Cloudy":   ("Cloudy", "Clear", "Overcast", "Windy"),
    "Overcast": ("Overcast", "Cloudy", "Rain", "Windy"),  # Snow appended in Fall/Winter
    "Windy":    ("Windy", "Clear", "Cloudy", "Overcast"),
    "Rain":     ("Rain", "Overcast", "Storm"),
    "Storm":    ("Storm", "Rain", "Overcast"),
    "Snow":     ("Snow", "Cloudy", "Overcast"),
}

# How long each weather state lasts, in in-game minutes (min, max inclusive).
_DURATION_RANGES = {
    "Clear":    (120, 300),
    "Cloudy":   ( 90, 240),
    "Overcast": ( 60, 180),
    "Windy":    ( 60, 150),
    "Rain":     ( 60, 180),
    "Storm":    ( 30,  90),
    "Snow":     ( 90, 240),
}

# Season-specific transition overrides keyed by (season, current_weather).
# Falls back to _TRANSITIONS for any unlisted combination.
# Repeated entries increase that outcome's probability.
_SEASONAL_TRANSITIONS = {
    # Spring: more Rain/Storm, more Windy
    ("Spring", "Clear"):    ("Clear", "Cloudy", "Windy", "Windy"),
    ("Spring", "Cloudy"):   ("Cloudy", "Clear", "Overcast", "Overcast", "Windy", "Windy"),
    ("Spring", "Overcast"): ("Overcast", "Cloudy", "Rain", "Rain", "Windy"),
    ("Spring", "Rain"):     ("Rain", "Rain", "Overcast", "Storm"),
    ("Spring", "Windy"):    ("Windy", "Windy", "Clear", "Cloudy", "Overcast"),

    # Summer: more Clear/Cloudy, harder to reach Rain
    ("Summer", "Clear"):    ("Clear", "Clear", "Cloudy", "Windy"),
    ("Summer", "Cloudy"):   ("Cloudy", "Cloudy", "Clear", "Clear", "Overcast", "Windy"),
    ("Summer", "Overcast"): ("Overcast", "Cloudy", "Cloudy", "Rain", "Windy"),

    # Fall: more Cloudy/Overcast (trending toward winter) and more Windy
    ("Fall", "Clear"):      ("Clear", "Cloudy", "Cloudy", "Windy", "Windy"),
    ("Fall", "Cloudy"):     ("Cloudy", "Cloudy", "Clear", "Overcast", "Overcast", "Windy", "Windy"),
    ("Fall", "Overcast"):   ("Overcast", "Overcast", "Cloudy", "Rain", "Windy"),
    ("Fall", "Windy"):      ("Windy", "Windy", "Clear", "Cloudy", "Overcast"),

    # Winter: more Cloudy/Overcast, less Clear
    ("Winter", "Clear"):    ("Clear", "Cloudy", "Cloudy", "Windy"),
    ("Winter", "Cloudy"):   ("Cloudy", "Cloudy", "Clear", "Overcast", "Overcast", "Windy"),
    ("Winter", "Overcast"): ("Overcast", "Overcast", "Cloudy", "Rain", "Windy"),
}

_COLD_SEASONS = ("Fall", "Winter")
_SNOW_TEMP_THRESHOLD = 4.0

# Meteor shower constants
# Large offset so shower PRNG doesn't correlate with weather PRNG at the same step
_METEOR_SEED_OFFSET = 0x100000

# Chance (%) that a meteor shower starts at any given weather transition, by season
_METEOR_SHOWER_CHANCE = {
    "Summer": 8,
    "Spring": 4,
    "Fall":   4,
    "Winter": 2,
}

# Shower duration range in in-game minutes (min >= one 3h forecast slot)
_METEOR_SHOWER_MIN_DURATION = 180
_METEOR_SHOWER_MAX_DURATION = 300


def _compute_meteor_shower(step, season):
    """
    Deterministically decide whether a meteor shower starts at this transition step.

    Returns (shower_active: bool, duration_minutes: int).
    Fully deterministic for a given (step, season).
    """
    x = _seeded_rand(step + _METEOR_SEED_OFFSET)
    chance = _METEOR_SHOWER_CHANCE.get(season, 4)
    if (x % 100) < chance:
        x = _xorshift32(x)
        span = _METEOR_SHOWER_MAX_DURATION - _METEOR_SHOWER_MIN_DURATION + 1
        duration = _METEOR_SHOWER_MIN_DURATION + (x % span)
        return True, duration
    return False, 0


def _compute_transition(step, current_weather, season, temperature=None):
    """
    Given a transition step index, current weather, season, and optional
    temperature (°C), return (next_weather, duration_minutes).

    temperature=None is treated as permissive (used during init before
    temperature is available). Snow is only reachable when temperature is
    at or below _SNOW_TEMP_THRESHOLD; Rain/Storm transition to Snow instead
    when cold enough.
    """
    x = _seeded_rand(step)

    options = _SEASONAL_TRANSITIONS.get((season, current_weather))
    if options is None:
        options = _TRANSITIONS.get(current_weather, ("Clear",))

    cold_enough = temperature is None or temperature <= _SNOW_TEMP_THRESHOLD
    if current_weather == "Overcast" and season in _COLD_SEASONS and cold_enough:
        options = options + ("Snow",)

    next_weather = options[x % len(options)]

    if cold_enough and next_weather in ("Rain", "Storm"):
        next_weather = "Snow"

    x = _xorshift32(x)
    min_d, max_d = _DURATION_RANGES.get(next_weather, (60, 180))
    duration = min_d + (x % (max_d - min_d + 1))

    return next_weather, duration


class WeatherSystem:
    """
    Manages automatic weather transitions over in-game time.

    State is stored entirely in context.environment so it persists across saves:
      - 'weather'       : current weather string
      - 'weather_step'  : int, global transition counter (seed for PRNG)
      - 'weather_timer' : float, in-game minutes remaining in current state

    Usage:
        ws = WeatherSystem()
        ws.update(game_minutes_elapsed, context.environment)
        forecast = ws.get_forecast(context.environment, hours=72)
    """

    def init_environment(self, environment, pet_seed):
        """
        Seed a fresh environment dict for a new game using pet_seed.

        Sets an initial weather_step offset so each pet's entire weather trajectory
        is unique, then derives the starting weather and timer from that step.
        The step range (0-16383) keeps us safely within the Markov chain's valid inputs.
        """
        from time_system import get_season

        # Use bits 8-21 of the seed as the starting step offset
        step = (pet_seed >> 8) & 0x3FFF

        # All pets start at the beginning of spring
        season_offset = 60
        environment['season_offset'] = season_offset
        environment['season'] = get_season(0, season_offset)

        season = environment['season']
        weather, duration = _compute_transition(step, 'Clear', season)
        environment['weather'] = weather
        environment['weather_step'] = step + 1
        environment['weather_timer'] = float(duration)
        environment['meteor_shower_timer'] = 0.0

    def update(self, game_minutes, environment):
        """
        Advance the weather simulation by game_minutes in-game minutes.

        If the current state's timer expires, transitions to the next state
        (possibly multiple times if game_minutes is large, e.g. after a save load).
        """
        if game_minutes <= 0:
            return

        timer = environment.get('weather_timer', 0.0)
        shower_timer = environment.get('meteor_shower_timer', 0.0) - game_minutes
        if shower_timer < 0:
            shower_timer = 0.0
        timer -= game_minutes

        while timer <= 0:
            step = environment.get('weather_step', 0)
            current = environment.get('weather', 'Clear')
            season = environment.get('season', 'Summer')
            shower_start, shower_dur = _compute_meteor_shower(step, season)
            if shower_start:
                shower_timer = max(shower_timer, float(shower_dur))
            temperature = environment.get('temperature', 20.0)
            next_weather, duration = _compute_transition(step, current, season, temperature)
            environment['weather'] = next_weather
            environment['weather_step'] = step + 1
            timer += duration

        environment['weather_timer'] = timer
        environment['meteor_shower_timer'] = shower_timer

    def get_forecast(self, environment, hours=72):
        """
        Return a deterministic weather forecast for the next `hours` in-game hours.

        Returns a list of (weather, duration_minutes, meteor_shower) tuples. The first
        entry is the current weather with its remaining time; subsequent entries are
        future states. The list covers at least `hours * 60` minutes of future time.
        """
        current = environment.get('weather', 'Clear')
        step = environment.get('weather_step', 0)
        remaining = environment.get('weather_timer', 60.0)
        season = environment.get('season', 'Summer')
        shower_timer = float(environment.get('meteor_shower_timer', 0.0))
        # Current temperature used as a fixed approximation across all forecast steps.
        temperature = float(environment.get('temperature', 20.0))

        forecast = [(current, int(remaining), shower_timer > 0)]
        total_minutes = remaining
        target_minutes = hours * 60

        # Advance shower timer past the current weather's remaining duration
        shower_timer = max(0.0, shower_timer - remaining)

        while total_minutes < target_minutes:
            shower_start, shower_dur = _compute_meteor_shower(step, season)
            if shower_start:
                shower_timer = max(shower_timer, float(shower_dur))
            next_weather, duration = _compute_transition(step, current, season, temperature)
            forecast.append((next_weather, duration, shower_timer > 0))
            total_minutes += duration
            current = next_weather
            step += 1
            shower_timer = max(0.0, shower_timer - duration)

        return forecast
