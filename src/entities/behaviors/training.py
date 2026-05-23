"""Training behavior - player-led exercise and skill session."""

import random
from entities.behaviors.base import BaseBehavior


class TrainingBehavior(BaseBehavior):
    """A structured training session with the player.

    Builds physical and mental stats over time. The pet finishes either
    energized enough to play or content to rest — their call.

    Phases:
    1. warming_up   - Gets into position and focused
    2. training     - The active session
    3. cooling_down - Wraps up, catches breath

    Rejection:
    - Cat holds a disinterested pose for ~5s then meanders away.
    """

    NAME = "training"

    _BONUSES = {
        "intelligence": {
            "energy": -3.0,
            "focus": -1.0,
            "playfulness": -4.0,
            "intelligence": 4.0,
            "couriosity": 2.5,
            "fulfillment": 2.0,
            "maturity": 1.0,
            "courage": 1.0,
            "sociability": 0.5,
            "loyalty": 1.0,
            "mischievousness": -1.0,
        },
        "behavior": {
            "energy": -3.5,
            "focus": -2.0,
            "playfulness": -5.0,
            "loyalty": 3.5,
            "courage": 2.5,
            "maturity": 2.0,
            "sociability": 1.5,
            "fulfillment": 2.0,
            "intelligence": 1.0,
            "fitness": 0.5,
            "couriosity": 0.5,
            "mischievousness": -1.5,
        },
        "fitness": {
            "energy": -5.0,
            "focus": -3.0,
            "playfulness": -8.0,
            "fitness": 5.0,
            "courage": 2.0,
            "fulfillment": 2.0,
            "loyalty": 1.0,
            "maturity": 0.5,
            "intelligence": 0.5,
            "sociability": 0.5,
            "couriosity": 0.5,
            "mischievousness": -0.5,
        },
        "sociability": {
            "energy": -2.0,
            "focus": -1.0,
            "playfulness": -3.0,
            "sociability": 4.0,
            "loyalty": 2.5,
            "fulfillment": 3.0,
            "courage": 1.5,
            "couriosity": 1.5,
            "intelligence": 1.0,
            "maturity": 0.5,
            "mischievousness": -0.5,
        },
    }

    # Fallback if an unrecognised type is passed.
    COMPLETION_BONUS = _BONUSES["behavior"]

    BEGGING_POSES = [
        "begging.side.arm_up",
        "begging.side.arm_up2",
        "begging.side.demanding",
    ]

    REJECTION_POSES = (
        "standing.side.neutral_looking_down",
        "sitting.side.looking_down",
        "laying.side.neutral2",
        "laying.side.bored",
        "sitting_silly.side.neutral",
        "standing.side.annoyed",
        "laying.side.annoyed",
        "laying.side.content",
        "sitting_licking.side.licking_leg",
    )

    REJECTION_DURATION = 5.0

    _REJECTION_THRESHOLDS = {
        "energy":      30,
        "focus":       30,
        "courage":     25,
        "sociability": 25,
    }

    @classmethod
    def _rejection_chance(cls, context):
        complement = 1.0
        for stat, threshold in cls._REJECTION_THRESHOLDS.items():
            val = getattr(context, stat, 100)
            if val < threshold:
                deficit = (threshold - val) / threshold
                complement *= (1.0 - deficit)
        return 1.0 - complement

    def get_completion_bonus(self, context):
        if self._rejecting:
            return {}
        return self._BONUSES.get(self._training_type, self.COMPLETION_BONUS)

    def __init__(self, character):
        super().__init__(character)
        self._training_type = "behavior"
        self._rejecting = False
        self.warmup_duration = random.uniform(1.0, 5.0)
        self.train_duration = random.uniform(10.0, 30.0)
        self.cooldown_duration = random.uniform(1.0, 5.0)
        self._begging_pair = []
        self._begging_index = 0
        self._pose_timer = 0.0
        self._pose_duration = 0.0

    def next(self, context):
        if self._rejecting:
            return 'meandering'
        if random.random() < 0.5:
            return 'playing'
        return None

    def start(self, on_complete=None, training_type="behavior"):
        if self._active:
            return
        self._training_type = training_type
        super().start(on_complete)

        context = self._character.context
        if context:
            self._rejecting = random.random() < self._rejection_chance(context)
        else:
            self._rejecting = False

        if self._rejecting:
            self._phase = "rejecting"
            self._character.set_pose(random.choice(self.REJECTION_POSES))
            return

        self._phase = "warming_up"
        idx = random.randint(0, 2)
        offset = random.randint(1, 2)
        self._begging_pair = [
            self.BEGGING_POSES[idx],
            self.BEGGING_POSES[(idx + offset) % 3],
        ]
        self._begging_index = 0
        self._pose_timer = 0.0
        self._pose_duration = random.uniform(1.5, 2.5)
        self._character.set_pose("standing.side.neutral")

    def update(self, dt):
        if not self._active:
            return

        self._phase_timer += dt

        if self._phase == "rejecting":
            if self._phase_timer >= self.REJECTION_DURATION:
                self.stop(completed=True)
            return

        if self._phase == "warming_up":
            if self._phase_timer >= self.warmup_duration:
                self._phase = "training"
                self._phase_timer = 0.0
                self._character.set_pose(self._begging_pair[0])

        elif self._phase == "training":
            self._pose_timer += dt
            if self._pose_timer >= self._pose_duration:
                self._begging_index = 1 - self._begging_index
                self._pose_timer = 0.0
                self._pose_duration = random.uniform(1.5, 2.5)
                self._character.set_pose(self._begging_pair[self._begging_index])

            self._progress = min(1.0, self._phase_timer / self.train_duration)
            if self._phase_timer >= self.train_duration:
                self._phase = "cooling_down"
                self._phase_timer = 0.0
                self._character.set_pose("sitting.side.looking_down")
                self._character.play_bursts()

        elif self._phase == "cooling_down":
            if self._phase_timer >= self.cooldown_duration:
                self._character.play_bursts()
                self.stop(completed=True)

