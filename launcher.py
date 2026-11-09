"""PyInstaller 打包入口（绝对导入，避免 __main__.py 相对导入问题）。

源码运行仍请使用：python -m docling_gui
"""

import sys

from docling_gui.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
