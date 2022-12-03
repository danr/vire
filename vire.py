from __future__ import annotations
from typing import *

from pathlib import Path
from queue import Queue
import argparse
import importlib
import os
import pty
import runpy
import signal
import sys
import termios
import threading
import tty

from inotify_simple import INotify, flags # type: ignore

STDIN_FILENO = sys.stdin.fileno()
STDOUT_FILENO = sys.stdout.fileno()

def spawn(f: Callable[[], None]) -> None:
    threading.Thread(target=f, daemon=True).start()

def sigterm(pid: int):
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

def getchar():
    # requires tty.setcbreak
    return sys.stdin.read(1)

def clear(clear_opt: int):
    # from entr: https://github.com/eradman/entr/blob/master/entr.c
    # 2J - erase the entire display
    # 3J - clear scrollback buffer
    # H  - set cursor position to the default
    if clear_opt == 1:
        print('\033[2J\033[H', end='', flush=True)
    if clear_opt >= 2:
        print('\033[2J\033[3J\033[H', end='', flush=True)

def run_child(argv: list[str], is_module: bool, clear_opt: int):
    sys.dont_write_bytecode = True
    sys.argv[1:] = argv[1:]
    clear(clear_opt)
    if is_module:
        runpy.run_module(argv[0], run_name='__main__')
    else:
        runpy.run_path(argv[0], run_name='__main__')

def main_inner(preload: str, argv: list[str], is_module: bool, glob_pattern: str, clear_opt: int=0):
    for name in preload.split(','):
        name = name.strip()
        if name:
            importlib.import_module(name)
    ino: Any = INotify()
    for name in Path('.').glob(glob_pattern):
        ino.add_watch(name, flags.MODIFY)
    q: Queue[Union[list[Any], str]] = Queue()
    @spawn
    def bg_getchar():
        while True:
            c = getchar()
            q.put_nowait(c)
    @spawn
    def bg_read_events():
        while True:
            q.put(ino.read(read_delay=1))
    while True:
        pid = fork(lambda: run_child(argv, is_module=is_module, clear_opt=clear_opt))
        try:
            msg = q.get()
        except KeyboardInterrupt:
            msg = 'q'
        sigterm(pid)
        if msg == 'q':
            sys.exit()

def fork(child: Callable[[], None]):
    pid, master_fd = pty.fork()

    if pid == 0:
        child()
        quit()

    @spawn
    def bg():
        # Copy pty master -> standard output   (master_read)
        while True:
            # Some OSes signal EOF by returning an empty byte string,
            # some throw OSErrors.
            try:
                data = os.read(master_fd, 1024)
            except OSError:
                data = b""
            if not data:  # Reached EOF.
                return    # Assume the child process has exited and is
                          # unreachable, so we clean up.
            else:
                os.write(STDOUT_FILENO, data)
        os.close(master_fd)
        os.waitpid(pid, 0)[1]

    return pid

def main():
    parser = argparse.ArgumentParser(
        description='''
            Runs a program and reruns it on updating files matching a glob (default **/*.py).
        ''',
        add_help=False,
    )
    parser.add_argument('--help', '-h', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--clear', '-c', action='count', default=0, help='Clear the screen before invoking the utility. Specify twice to erase the scrollback buffer.')
    parser.add_argument('--preload', '-p', metavar='M', help='Modules to preload, comma-separated. Example: flask,pandas')
    parser.add_argument('--glob', '-g', metavar='G', help='Watch for updates to files matching this glob, Default: **/*.py', default='**/*.py')
    parser.add_argument('-m', action='store_true', help='Argument is a module, will be run like python -m (using runpy)')
    parser.add_argument(dest='argv', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if not args.argv or args.help:
        parser.print_help()
        quit()

    mode = termios.tcgetattr(STDIN_FILENO)
    try:
        tty.setcbreak(STDIN_FILENO) # required for returning single characters from standard input
        main_inner(
            args.preload or '',
            args.argv,
            is_module=args.m,
            glob_pattern=args.glob,
            clear_opt=args.clear,
        )
    finally:
        termios.tcsetattr(STDIN_FILENO, termios.TCSAFLUSH, mode)

if __name__ == '__main__':
    main()
