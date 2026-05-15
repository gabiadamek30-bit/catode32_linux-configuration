from scene import Scene
from settings import Settings, SettingItem


STATS = [
    ("Fullness",      "fullness"),
    ("Energy",        "energy"),
    ("Comfort",       "comfort"),
    ("Playfulness",   "playfulness"),
    ("Focus",         "focus"),
    ("Health",        "health"),
    ("Fulfillment",   "fulfillment"),
    ("Cleanliness",   "cleanliness"),
    ("Curiosity",     "curiosity"),
    ("Sociability",   "sociability"),
    ("Intelligence",  "intelligence"),
    ("Maturity",      "maturity"),
    ("Affection",     "affection"),
    ("Fitness",       "fitness"),
    ("Serenity",      "serenity"),
    ("Courage",       "courage"),
    ("Loyalty",       "loyalty"),
    ("Mischief",      "mischievousness"),
]

_DEBUG_ONLY = [
    ("Sickness",      "sickness",      0,   10),
]


class DebugStatsScene(Scene):
    """Debug scene for directly editing pet stats"""

    def __init__(self, context, renderer, input):
        super().__init__(context, renderer, input)
        self.settings = Settings(renderer, input)

    def load(self):
        super().load()

    def unload(self):
        super().unload()

    def enter(self):
        items = [
            SettingItem(
                name, key,
                min_val=0, max_val=100, step=1,
                value=int(getattr(self.context, key, 50))
            )
            for name, key in STATS
        ]
        for name, key, mn, mx in _DEBUG_ONLY:
            items.append(SettingItem(
                name, key,
                min_val=mn, max_val=mx, step=1,
                value=int(getattr(self.context, key, 0))
            ))
        self.settings.open(items, transition=False)

    def exit(self):
        pass

    def update(self, dt):
        pass

    def draw(self):
        self.settings.draw()

    def handle_input(self):
        result = self.settings.handle_input()
        if result is not None:
            for key, value in result.items():
                setattr(self.context, key, float(value))
            return ('change_scene', 'last_main')
        return None
