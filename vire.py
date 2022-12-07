from __future__ import annotations
from typing import *
from dataclasses import dataclass

from pathlib import Path
from queue import Queue
import argparse
import importlib
import os
import runpy
import signal
import sys
import termios
import threading
import tty
import traceback

from inotify_simple import INotify, flags # type: ignore

STDIN_FILENO = sys.stdin.fileno()
STDOUT_FILENO = sys.stdout.fileno()

def spawn(f: Callable[[], None]) -> None:
    threading.Thread(target=f, daemon=True).start()

def sigterm(pid: int):
    try:
        os.kill(pid, signal.SIGTERM)
        os.waitpid(pid, 0)
    except ProcessLookupError:
        pass

def clear(clear_opt: int):
    # from entr: https://github.com/eradman/entr/blob/master/entr.c
    # 2J - erase the entire display
    # 3J - clear scrollback buffer
    # H  - set cursor position to the default
    if clear_opt == 1:
        print('\033[2J\033[H', end='', flush=True)
    if clear_opt >= 2:
        print('\033[2J\033[3J\033[H', end='', flush=True)

def run_child(argv: list[str], is_module: bool):
    sys.dont_write_bytecode = True
    sys.argv[1:] = argv[1:]
    try:
        if is_module:
            runpy.run_module(argv[0], run_name='__main__')
        else:
            runpy.run_path(argv[0], run_name='__main__')
    except:
        traceback.print_exc()

@dataclass
class Vire:
    preload:          str
    argv:             list[str]
    is_module:        bool
    glob_patterns:    str
    clear_opt:        int = 0
    silent:           bool = False
    auto_full_reload: bool = False
    _restore:         Callable[[], None] = lambda: None

    def main(self):
        mode = termios.tcgetattr(STDIN_FILENO)
        self._restore = lambda: termios.tcsetattr(STDIN_FILENO, termios.TCSAFLUSH, mode)
        try:
            tty.setcbreak(STDIN_FILENO) # required for returning single characters from standard input
            self._main()
        finally:
            self._restore()

    def getchar(self):
        # requires tty.setcbreak
        return sys.stdin.read(1)

    def _main(self):
        for name in self.preload.split(','):
            name = name.strip()
            if name:
                try:
                    importlib.import_module(name)
                except:
                    traceback.print_exc()
        imported_at_preload: set[str] = {
            file
            for _, m in sys.modules.items()
            for file in [getattr(m, '__file__', None)]
            if file
            if not file.startswith('/usr')
        }
        wd_to_filename: dict[int, str] = {}
        ino: Any = INotify()
        def add_watch(filename: str | Path):
            wd = ino.add_watch(filename, flags.MODIFY)
            wd_to_filename[wd] = str(Path(filename).resolve())
        for name in imported_at_preload:
            add_watch(name)
        for glob_pattern in self.glob_patterns.split(','):
            for name in Path('.').glob(glob_pattern.strip()):
                add_watch(name)
        out_of_sync: set[str] = set()
        q: Queue[Union[set[str], str]] = Queue()
        @spawn
        def bg_getchar():
            while True:
                c = self.getchar()
                q.put_nowait(c)
        @spawn
        def bg_read_events():
            nonlocal out_of_sync
            while True:
                events = ino.read(read_delay=1)
                files = {wd_to_filename[e.wd] for e in events}
                out_of_sync |= files & imported_at_preload
                msg = files - imported_at_preload
                q.put(msg)
        while True:
            clear(self.clear_opt)
            pid = fork(lambda: run_child(self.argv, is_module=self.is_module))
            out_of_sync_reported: set[str] = set()
            while True:
                if not self.silent and out_of_sync != out_of_sync_reported:
                    print('vire: Preloaded files have been modified:', file=sys.stderr)
                    print(*['        ' + f for f in out_of_sync], sep='\n', file=sys.stderr)
                    print('      Press R for full reload.', file=sys.stderr)
                    out_of_sync_reported = set(out_of_sync)
                try:
                    msg = q.get()
                except KeyboardInterrupt:
                    msg = 'q'
                if self.auto_full_reload and out_of_sync:
                    print('vire: Preloaded files have been modified:', file=sys.stderr)
                    print(*['        ' + f for f in out_of_sync], sep='\n', file=sys.stderr)
                    print('      Running full reload.', file=sys.stderr)
                    msg = 'R-auto'
                if msg == 'q':
                    sigterm(pid)
                    sys.exit()
                if msg == 'R' or msg == 'R-auto':
                    sigterm(pid)
                    clear(1 if msg == 'R' else self.clear_opt)
                    self._restore()
                    max_fd = os.sysconf("SC_OPEN_MAX")
                    os.closerange(3, max_fd)
                    os.execve(sys.argv[0], sys.argv, os.environ)
                if msg == 'c':
                    clear(1)
                    break
                if msg == 'C':
                    clear(2)
                    break
                if msg == ' ' or msg == 'r':
                    break
                if isinstance(msg, set) and msg:
                    break
            sigterm(pid)

def fork(child: Callable[[], None]):
    pid = os.fork()

    if pid == 0:
        os.dup2(os.open('/dev/null', os.O_RDONLY), STDIN_FILENO)
        child()
        quit()

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
    parser.add_argument('--silent', '-s', action='store_true', help='Silence warning about modifications to preloaded modules.')
    parser.add_argument('--auto-full-reload', '-r', action='store_true', help='Automatically do full reload on modifications to preloaded modules.')
    parser.add_argument('-m', action='store_true', help='Argument is a module, will be run like python -m (using runpy)')
    parser.add_argument(dest='argv', nargs=argparse.REMAINDER)
    args = parser.parse_args()

    if not args.argv or args.help:
        parser.print_help()
        quit()

    Vire(
        preload          = args.preload or '',
        argv             = args.argv,
        is_module        = args.m,
        glob_patterns    = args.glob,
        clear_opt        = args.clear,
        silent           = args.silent,
        auto_full_reload = args.auto_full_reload,
    ).main()

if __name__ == '__main__':
    main()
