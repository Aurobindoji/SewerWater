"""python -m launcher [--no-browser]: the start page (language, sewer / water) - the module chosen alone starts."""
import sys

from launcher.server import main

main(sys.argv[1:])
