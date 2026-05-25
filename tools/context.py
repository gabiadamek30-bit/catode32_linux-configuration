#!/usr/bin/env python3
"""
Import or export the pet's save file (context) to/from the device.

Usage:
    ./tools/context.py --export context.json
    ./tools/context.py --import context.json
    ./tools/context.py --export context.json --port /dev/tty.usbserial-0001
    ./tools/context.py --import context.json --port /dev/tty.usbserial-0001
    ./tools/context.py --backups
    ./tools/context.py --backups --port /dev/tty.usbserial-0001
"""

import argparse
import subprocess
import sys

_DEVICE_SAVE_PATH = '/save.json'
_DEVICE_BACKUP_PATHS = ['/backup.json', '/backup.old.json']


def _run_mp(port, args):
    """Run an mpremote command, optionally targeting a specific port."""
    cmd = ['mpremote']
    if port:
        cmd += ['connect', port]
    cmd += args
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stderr.strip(), file=sys.stderr)
        sys.exit(1)
    return result.stdout


def export(path, port):
    print(f'Exporting {_DEVICE_SAVE_PATH} -> {path}')
    # Use exec instead of fs cp: fs cp sends its helper script via raw paste mode
    # which is mishandled on this firmware/mpremote combination, while exec uses
    # standard raw REPL which works fine.
    output = _run_mp(port, ['resume', 'exec',
        f"f=open('{_DEVICE_SAVE_PATH}');d=f.read();f.close();print(d,end='')",
        '+', 'reset'])
    with open(path, 'w') as f:
        f.write(output)
    print('Done.')


def import_(path, port):
    print(f'Importing {path} -> {_DEVICE_SAVE_PATH}')
    with open(path) as f:
        json_data = f.read()
    # Embed the JSON as a Python string literal so the whole operation is one
    # exec call (no raw paste mode), then chain reset in the same connection.
    code = f"f=open('{_DEVICE_SAVE_PATH}','w');f.write({repr(json_data)});f.close();import uos;uos.sync()"
    _run_mp(port, ['resume', 'exec', code, '+', 'reset'])
    print('Done.')


def export_backups(port):
    for device_path in _DEVICE_BACKUP_PATHS:
        local_name = device_path.lstrip('/')
        print(f'Exporting {device_path} -> {local_name}')
        result = subprocess.run(
            (['mpremote'] + (['connect', port] if port else []) +
             ['resume', 'exec',
              f"try:\n f=open('{device_path}');d=f.read();f.close();print(d,end='')\nexcept OSError:print('__NOT_FOUND__',end='')",
              '+', 'reset']),
            capture_output=True, text=True)
        if result.returncode != 0:
            print(f'  Warning: could not read {device_path} — skipping', file=sys.stderr)
            continue
        if result.stdout == '__NOT_FOUND__':
            print(f'  {device_path} not found on device — skipping')
            continue
        with open(local_name, 'w') as f:
            f.write(result.stdout)
    print('Done.')


def main():
    parser = argparse.ArgumentParser(description='Import/export pet context (save file).')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--export', metavar='FILE', help='Copy save file from device to FILE')
    group.add_argument('--import', metavar='FILE', dest='import_', help='Copy FILE to device and reboot')
    group.add_argument('--backups', action='store_true', help='Copy backup.json and backup.old.json from device to current directory')
    parser.add_argument('--port', metavar='PORT', help='Serial port (e.g. /dev/tty.usbserial-0001)')
    args = parser.parse_args()

    if args.export:
        export(args.export, args.port)
    elif args.import_:
        import_(args.import_, args.port)
    else:
        export_backups(args.port)


if __name__ == '__main__':
    main()
