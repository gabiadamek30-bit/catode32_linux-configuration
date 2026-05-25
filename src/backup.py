"""Pet backup — records adopted-pet seeds and periodic stat snapshots.

backup.json  — current pet's backup, written at adoption and updated every
               _SNAPSHOT_INTERVAL_DAYS in-game days with the latest stats.
backup.old.json — previous pet's backup; written once on the next adoption and
               never touched again by this system.

This module is lazy-loaded and immediately unloaded (sys.modules.pop) by its
callers so it doesn't occupy RAM during normal gameplay.
"""

import ujson
import uos

_BACKUP_PATH     = '/backup.json'
_BACKUP_OLD_PATH = '/backup.old.json'

_SNAPSHOT_INTERVAL_DAYS = 35

_SNAPSHOT_STAT_KEYS = (
    'fullness', 'energy', 'comfort', 'playfulness', 'focus',
    'fulfillment', 'cleanliness', 'curiosity', 'sociability',
    'intelligence', 'maturity', 'affection',
    'fitness', 'serenity',
    'courage', 'loyalty', 'mischievousness',
    'zoomies_high_score', 'maze_best_time', 'snake_high_score',
    'memory_best_score', 'hanjie_best_time',
)

_IDENTITY_KEYS = (
    'pet_gender', 'fav_weather', 'star_sign',
    'fav_meal', 'least_fav_meal',
    'fav_snack', 'least_fav_snack',
    'fav_toy', 'least_fav_toy',
    'fav_location', 'least_fav_location',
)


def write_adoption(candidates, adopted_seed, adopted_name):
    """Rotate backup.json -> backup.old.json, then write a fresh backup.json."""
    try:
        uos.rename(_BACKUP_PATH, _BACKUP_OLD_PATH)
    except OSError:
        pass
    data = {
        'candidates': [c['seed'] for c in candidates],
        'adopted_seed': adopted_seed,
        'adopted_name': adopted_name,
        'last_snapshot_day': 0,
        'snapshot': None,
    }
    try:
        with open(_BACKUP_PATH, 'w') as f:
            ujson.dump(data, f)
        uos.sync()
        print('[Backup] Written: ' + adopted_name)
    except Exception as e:
        print('[Backup] Write failed: ' + str(e))


def maybe_write_snapshot(context):
    """Overwrite the snapshot in backup.json if 35+ in-game days have passed."""
    day = context.environment.get('day_number', 0)
    try:
        with open(_BACKUP_PATH) as f:
            data = ujson.load(f)
    except OSError:
        return
    except Exception as e:
        print('[Backup] Read failed: ' + str(e))
        return
    if day - data.get('last_snapshot_day', 0) < _SNAPSHOT_INTERVAL_DAYS:
        return
    snap = {'day': day, 'name': context.pet_name, 'seed': context.pet_seed}
    for k in _SNAPSHOT_STAT_KEYS:
        snap[k] = getattr(context, k, None)
    for k in _IDENTITY_KEYS:
        snap[k] = getattr(context, k, None)
    data['snapshot'] = snap
    data['last_snapshot_day'] = day
    try:
        with open(_BACKUP_PATH, 'w') as f:
            ujson.dump(data, f)
        uos.sync()
        print('[Backup] Snapshot at day ' + str(day))
    except Exception as e:
        print('[Backup] Snapshot failed: ' + str(e))
