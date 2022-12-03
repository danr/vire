# vire: viable reloader

Reruns your python program when source files changes, with the possibility to preload libraries.

```
$ vire -h
usage: vire [--clear] [--preload M] [--glob G] [-m] ...

Runs a program and reruns it on updating files matching a glob (default **/*.py).

positional arguments:
  argv

options:
  --clear, -c        Clear the screen before invoking the utility. Specify twice to erase the scrollback
                     buffer.
  --preload M, -p M  Modules to preload, comma-separated. Example: flask,pandas
  --glob G, -g G     Watch for updates to files matching this glob, Default: **/*.py
  -m                 Argument is a module, will be run like python -m (using runpy)
```
