# 钻孔数据编辑工具 v3

v3 以 v2 为兼容基线，保留原有界面、菜单、快捷键、操作流程和项目文件格式，仅优化内部结构、性能、稳定性和自动化测试。可见版本标识更新为 v3。

## 运行

在 Windows 上双击 `run.py`，或在本目录执行：

```powershell
python run.py
```

项目需要 Python 3.10+、PySide6 6.6+ 和 openpyxl 3.1+。

## 剖面图和柱状图

- 左侧树中的“剖面图”显示 `H1`、`Z1` 等剖面文件组。右键剖面主文件可重命名，主文件及同名前缀的 `.-d0`、`.-g`、`.-k` 等附属文件会在保存时作为一个整体更新。
- “柱状图”中的 `0yzk.-zkt` 保存全部岩钻孔编号，`0nzk.-zkt` 保存全部土钻孔编号。内容按钻孔号自然排序，每行一个编号，最后一行为 `★`。
- 加载项目时如果两个柱状图文件缺失，v3 会在内存中自动生成并列入待保存内容；只有执行“保存数据”后才写入磁盘。
- 新增、复制、删除或修改钻孔编号后，两个柱状图会自动同步；保存前会再次规范化，避免手工编辑造成编号遗漏。

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
python tools/hash_tree.py ..\v2 --check v2-baseline.sha256
```

v3 不在运行时导入 v2，也不得修改 v2 的任何文件。
