# 🔁 vire: viable reloader

Reruns your python program when source files changes, with the possibility to preload libraries.

    $ vire -h
    usage: vire [--clear] [--preload M] [--glob G] [--silent] [--auto-full-reload] [-m] ...


### Installation:

    pip install git+https://github.com/danr/vire.git

### Options:

    --clear, -c              Clear the screen before invoking the utility.
                             Specify twice to erase the scrollback buffer.
    --preload M, -p M        Modules to preload, comma-separated. Example: flask,pandas
    --glob G, -g G           Watch for updates to files matching this glob, Default: **/*.py
    --silent, -s             Silence warning about modifications to preloaded modules.
    --auto-full-reload, -r   Automatically do full reload on modifications to preloaded modules.
    -m                       Argument is a module, will be run like python -m (using runpy)

### Keybindings:

<table>
<tr><td><tt>r, &lt;space>  <td>reload
<tr><td><tt>R              <td>full reload: reloads all preloaded modules
<tr><td><tt>c              <td>reload with clear screen
<tr><td><tt>C              <td>reload with clear screen and scrollback buffer
<tr><td><tt>q, &lt;ctrl-c> <td>quit
</table>
