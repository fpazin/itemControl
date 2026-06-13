from __future__ import annotations

import argparse

from itemcontrol import __version__
from itemcontrol.ui import main as ui_main


def cli_main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ItemControl")
    parser.add_argument(
        "--version",
        action="version",
        version=f"ItemControl {__version__}",
    )
    parser.parse_args(argv)
    return ui_main()

if __name__ == "__main__":
    raise SystemExit(cli_main())
