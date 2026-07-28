# v3 自动同步孔深持久化修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 基础数据最深层深度变化后，把自动同步的主文件孔深纳入保存和撤销重做事务。

**Architecture:** `MainFilePage` 在自动孔深变化时复用既有 `field_changed` 信号，由 `MainWindow` 按现有路径标记 `main`。`BasicDataPage` 将普通编辑的完成快照延后到全部联动信号结束之后，使层数据和主文件孔深进入同一撤销操作。

**Tech Stack:** Python 3.10+、PySide6、pytest、pytest-qt、Ruff、mypy、PyInstaller。

---

### Task 1: 复现保存后主文件孔深回退

**Files:**
- Create: `v3/tests/ui/test_depth_sync.py`

- [ ] **Step 1: 写保存并重新加载测试**

建立孔深 `12.5`、最深层 `12.5` 的磁盘项目，通过基础数据模型把最深层改为 `14`，断言：

```python
assert borehole.main.depth == "14.0"
assert {"c", "main"} <= borehole.dirty_suffixes
SaveService(project).save()
reloaded = load_project(folder).boreholes["ZK1"]
assert reloaded.main.depth == "14.0"
assert reloaded.layers[-1].bottom_depth == "14.0"
```

- [ ] **Step 2: 写撤销重做测试**

编辑后撤销，断言主孔深和最深层均回到 `12.5`；重做后两者均为 `14.0`，且 `main` 仍在脏后缀中。

- [ ] **Step 3: 运行测试确认 RED**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_depth_sync.py -q`

Expected: 保存测试缺少 `main` 脏后缀；重做测试得到新层底深度和旧主文件孔深。

### Task 2: 修复自动同步的脏标记和快照顺序

**Files:**
- Modify: `v3/src/borehole/ui/main_file_page.py`
- Modify: `v3/src/borehole/ui/basic_data_page.py`

- [ ] **Step 1: 自动同步后发出主文件字段变化**

在 `_sync_depth_from_layers()` 保存旧孔深，更新模型和输入框后发出：

```python
self.field_changed.emit(1, old_depth, formatted)
```

- [ ] **Step 2: 联动完成后拍摄撤销快照**

`BasicDataPage._on_after_edit()` 先取出并清空编辑令牌，调用 `_mark_all_dirty()` 完成孔深联动，再把令牌传给 `_end_change()`。

- [ ] **Step 3: 运行目标测试确认 GREEN**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_depth_sync.py tests/ui/test_stability_behavior.py tests/unit/test_undo_manager.py -q`

Expected: all pass。

### Task 3: 完整验证与交付

**Files:**
- Modify: `v3/COMPATIBILITY.md`

- [ ] **Step 1: 更新兼容性报告**

记录自动孔深保存、重新加载和撤销重做行为，并把 pytest 数量更新为实际值。

- [ ] **Step 2: 运行质量门槛**

Run: pytest `-W error`、Ruff、mypy、v2 哈希检查。

Expected: 全部 exit 0，v2 清单 124 个文件一致。

- [ ] **Step 3: 构建和冒烟 EXE**

Run: PyInstaller 构建并隐藏启动 EXE，确认窗口标题为“钻孔数据编辑工具 v3”、进程响应且能正常关闭。

Expected: 构建成功且无残留进程。
