from __future__ import annotations

import argparse
from pathlib import Path

from spspec.core import main as core_main


def main(argv: list[str] | None = None) -> int:
    return core_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
