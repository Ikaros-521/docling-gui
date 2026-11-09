"""python -m docling_gui 入口（实现见 cli 模块）。"""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
