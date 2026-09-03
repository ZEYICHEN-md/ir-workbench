"""港股市场内部查询域。

Python 3.14 在部分 Windows 11 机器上会让 ``platform.machine()`` 走 WMI；
本机 WMI 查询会无限等待，pandas 导入也因此卡死。禁用私有 WMI 快路径后，
stdlib 会回退到 ``sys.getwindowsversion`` 与环境变量，足够判断 pandas 的平台常量。
"""

from __future__ import annotations

import platform
import sys

if sys.platform == "win32" and sys.version_info >= (3, 14) and hasattr(platform, "_wmi"):
    platform._wmi = None
