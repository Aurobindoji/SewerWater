"""python -m water_app ui [--port 8766] [--no-browser]: the water module's map page on its own server."""
import sys

from .server import main

if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "ui":
        args = args[1:]
    main(args)
