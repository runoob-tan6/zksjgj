"""启动入口 - 双击运行此文件启动应用。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from borehole.main import main

if __name__ == "__main__":
    main()
