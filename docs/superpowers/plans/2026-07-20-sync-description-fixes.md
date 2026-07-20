# v3 同步描述修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复岩性描述同步的空地层时代误匹配、提示覆盖和跨钻孔撤销后无法重做问题。

**Architecture:** 保留现有 UI 信号链和每钻孔撤销管理器。通过调整描述信号的发出顺序、统一同步动作类型并让复合快照恢复不改变当前钻孔，以最小范围修复行为。

**Tech Stack:** Python 3.10+、PySide6、pytest、pytest-qt、Ruff、mypy。

---

### Task 1: 锁定同步匹配规则

**Files:**
- Create: `v3/tests/ui/test_description_sync.py`
- Modify: `v3/src/borehole/ui/main_window.py:938-984`

- [ ] **Step 1: 写空地层时代严格匹配测试**

构造源层地层时代为空、两个目标层分别为空和 `Q4`，调用 `_sync_description()` 后只允许空地层时代目标收到描述。另断言相同三项但已有描述的目标不被覆盖，收到描述的目标包含 `h` 脏后缀。

```python
window._sync_description("同步文本", "3-2", "", "强风化")

assert blank_target.layers[0].description == "同步文本"
assert q4_target.layers[0].description == ""
assert filled_target.layers[0].description == "已有描述"
assert blank_target.dirty_suffixes == {"h"}
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py::test_sync_requires_exact_formation_and_preserves_existing_descriptions -q`

Expected: FAIL，`Q4` 目标被错误写入。

- [ ] **Step 3: 实现严格三项匹配**

把 `_sync_description()` 中的地层时代判断改为：

```python
layer.formation == formation
```

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py::test_sync_requires_exact_formation_and_preserves_existing_descriptions -q`

Expected: PASS。

### Task 2: 修复同步提示和撤销入栈顺序

**Files:**
- Modify: `v3/tests/ui/test_description_sync.py`
- Modify: `v3/src/borehole/ui/basic_data_page.py:95-103`
- Modify: `v3/src/borehole/ui/main_window.py:973-980`

- [ ] **Step 1: 写表格编辑后的最终提示测试**

通过 `BasicLayerModel.setData()` 编辑源层描述，断言同步完成后最终状态为同步数量提示，并且源编辑动作先于同步复合动作进入源钻孔撤销栈。

```python
index = window._main_file_page._basic_data_page._model.index(0, 6)
assert window._main_file_page._basic_data_page._model.setData(index, "同步文本")

assert window._status_label.text() == "已同步岩性描述到 1 个钻孔。"
assert isinstance(manager.undo_stack[-1], CompositeUndoAction)
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py::test_table_edit_keeps_sync_status_and_records_sync_last -q`

Expected: FAIL，最终提示为普通修改提示，最后一个动作不是同步复合动作。

- [ ] **Step 3: 调整事件顺序并统一复合动作**

在 `BasicLayerModel.setData()` 中先调用 `after_set_data`，再调用 `on_description_changed`。`_sync_description()` 对一个或多个目标统一执行：

```python
manager.push_composite(CompositeUndoAction(actions=actions, label="同步岩性描述"))
```

- [ ] **Step 4: 运行测试确认 GREEN**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py::test_table_edit_keeps_sync_status_and_records_sync_last -q`

Expected: PASS。

### Task 3: 修复跨钻孔撤销和重做

**Files:**
- Modify: `v3/tests/ui/test_description_sync.py`
- Modify: `v3/src/borehole/ui/main_window.py:1016-1060`

- [ ] **Step 1: 写单目标和多目标撤销重做测试**

表格编辑同步后，第一次撤销只清空所有目标描述且保持源孔为当前钻孔；重做按钮可用，重做后恢复所有目标描述并仍保持源孔。分别覆盖一个和两个目标钻孔。

```python
window._undo()
assert window._current_borehole is source
assert window._redo_action.isEnabled()
assert all(not target.layers[0].description for target in targets)

window._redo()
assert window._current_borehole is source
assert all(target.layers[0].description == "同步文本" for target in targets)
```

- [ ] **Step 2: 运行测试确认 RED**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py -q`

Expected: FAIL，撤销后当前钻孔切换且重做不可用。

- [ ] **Step 3: 为复合动作增加非激活快照恢复**

扩展 `_apply_snapshot()`：

```python
def _apply_snapshot(self, borehole: Borehole, snapshot: BoreholeSnapshot, *, activate: bool = True) -> None:
    ...
    if not activate:
        return
    self._current_borehole = borehole
    ...
```

复合撤销/重做使用 `activate=False`，全部恢复后只刷新树并保持源钻孔选中。普通单钻孔动作继续使用默认行为。

- [ ] **Step 4: 运行专项回归确认 GREEN**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py tests/ui/test_profile_column_chart_ui.py tests/ui/test_stability_behavior.py -q`

Expected: all pass。

### Task 4: 全量验证与交付

**Files:**
- Modify: `v3/COMPATIBILITY.md`

- [ ] **Step 1: 记录同步描述修复证据**

在兼容性报告中记录严格匹配、已有描述保护、跨孔撤销重做和专项测试。

- [ ] **Step 2: 运行完整质量门槛**

```powershell
cd v3
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider -W error -q
python -m ruff check src tests tools
python -m mypy src tools
python tools/hash_tree.py 'F:\钻孔数据工具\v2' --check v2-baseline.sha256
```

Expected: 全部 exit 0，v2 验证 124 个文件。

- [ ] **Step 3: 构建并冒烟测试 EXE**

Run: `cd v3; python -m PyInstaller --clean --noconfirm borehole_v3.spec`

Expected: 构建成功，启动后窗口标题为“钻孔数据编辑工具 v3”，标准关闭消息后进程退出。

- [ ] **Step 4: 提交、合并和清理**

提交源码、测试和兼容性报告；快进合并到 `main`，在合并结果上重新运行质量门槛，复制已验证 EXE 到主工作区并清理功能工作树。
