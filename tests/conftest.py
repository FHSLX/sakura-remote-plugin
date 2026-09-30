"""Sakura 的隔离 Runtime 不会自动把工作目录加入 Python 导入路径。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
