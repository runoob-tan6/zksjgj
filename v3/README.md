# 钻孔数据编辑工具 v3

v3 以 v2 为兼容基线，保留原有界面、菜单、快捷键、操作流程和项目文件格式，仅优化内部结构、性能、稳定性和自动化测试。可见版本标识更新为 v3。

## 运行

在 Windows 上双击 `run.py`，或在本目录执行：

```powershell
python run.py
```

项目需要 Python 3.10+、PySide6 6.6+ 和 openpyxl 3.1+。

## 测试

```powershell
python -m pytest -p no:cacheprovider -q
python -m ruff check src tests tools
python -m mypy src tools
```

## 打包

双击 `打包exe.bat`，或执行：

```powershell
python -m PyInstaller --clean --noconfirm borehole_v3.spec
```

输出文件为 `dist/钻孔数据编辑工具v3.exe`。

## v2 保护

`v2-baseline.sha256` 记录开发开始时 v2 的全部文件路径、大小和 SHA-256。验收时运行：

```powershell
python tools/hash_tree.py ../../v2 --check v2-baseline.sha256
```

v3 不在运行时导入 v2，也不得修改 v2 的任何文件。
