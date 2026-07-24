# v3 剖面图自然数值排序 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 剖面图列表按名称数字部分的整数值排序，使 `H2` 显示在 `H10` 之前。

**Architecture:** 在主窗口模块增加只负责剖面名称的私有排序键，并在构建“剖面图”树节点时使用。测试从真实 `QTreeWidget` 读取显示顺序，锁定用户可见行为。

**Tech Stack:** Python 3.10+、PySide6、pytest、pytest-qt、Ruff、mypy、PyInstaller。

---

### Task 1: 锁定剖面列表自然顺序

**Files:**
- Modify: `v3/tests/ui/test_profile_column_chart_ui.py`

- [ ] **Step 1: 写失败的 UI 测试**

构造 `H10、H2、H1、Z10、Z2、Z1` 六个剖面模型，刷新列表并读取“剖面图”节点子项：

```python
assert labels == ["H1", "H2", "H10", "Z1", "Z2", "Z10"]
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_profile_column_chart_ui.py::test_profile_list_uses_natural_numeric_order -q`

Expected: FAIL，实际字符串顺序为 `H1、H10、H2、Z1、Z10、Z2`。

### Task 2: 实现剖面名称排序键

**Files:**
- Modify: `v3/src/borehole/ui/main_window.py`

- [ ] **Step 1: 增加私有排序键**

合法名称返回 `(0, 字母前缀, 整数编号, 原名称)`；异常名称返回 `(1, "", 0, 小写名称)`，使异常数据排在合法名称之后且不会报错。

- [ ] **Step 2: 应用到剖面树节点**

把剖面名称循环改为：

```python
for name in sorted(self._project.profile_files, key=_profile_sort_key):
```

- [ ] **Step 3: 运行目标测试确认 GREEN**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_profile_column_chart_ui.py -q`

Expected: all pass。

### Task 3: 完整验证与交付

**Files:**
- Modify: `v3/COMPATIBILITY.md`

- [ ] **Step 1: 更新兼容性报告**

记录剖面图自然数值排序，并把 pytest 数量更新为实际值。

- [ ] **Step 2: 运行质量门槛**

Run: pytest `-W error`、Ruff、mypy、v2 哈希检查。

Expected: 全部 exit 0，v2 清单 124 个文件一致。

- [ ] **Step 3: 构建和冒烟 EXE**

Run: PyInstaller 构建并隐藏启动 EXE，确认窗口标题为“钻孔数据编辑工具 v3”、进程响应且能正常关闭。

Expected: 构建成功且无残留进程。
