# v3 相同地层描述确认同步 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 编辑岩性描述时，提示用户是否同步更新其他钻孔中与修改前文本完全相同的同地层描述。

**Architecture:** 描述编辑信号增加修改前文本参数。主窗口按严格地层条件把其他层分为空描述、相同旧描述和其他描述三类，只对相同旧描述候选弹出一次确认，并复用现有复合撤销事务。

**Tech Stack:** Python 3.10+、PySide6、pytest、pytest-qt、Ruff、mypy。

---

### Task 1: 锁定确认与拒绝行为

**Files:**
- Modify: `v3/tests/ui/test_description_sync.py`
- Modify: `v3/src/borehole/ui/basic_data_page.py`
- Modify: `v3/src/borehole/ui/main_file_page.py`
- Modify: `v3/src/borehole/ui/main_window.py`

- [ ] **Step 1: 写确认同步测试**

源描述从“原描述”改为“新描述”，其他钻孔包含空描述、原描述和不同描述。模拟确认框返回 `Yes`，断言空描述和原描述都更新，不同描述不变，提示只调用一次且包含相同描述数量。

```python
assert blank_target.layers[0].description == "新描述"
assert same_target.layers[0].description == "新描述"
assert different_target.layers[0].description == "不同描述"
assert prompts == ["发现 1 处其他钻孔的相同地层描述仍为修改前内容。\n\n是否全部同步为新描述？"]
```

- [ ] **Step 2: 写拒绝同步和无候选测试**

返回 `No` 时只自动填充空描述，原描述目标保持不变。没有相同非空候选时设置一个会抛错的确认框替身，证明不会弹窗。

- [ ] **Step 3: 运行测试确认 RED**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py -q`

Expected: 新增测试失败，因为当前信号没有旧描述且不会弹窗或更新非空相同描述。

- [ ] **Step 4: 扩展描述信号参数**

把描述回调和信号统一为：

```python
(old_description, description, lithology_code, formation, weathering)
```

`BasicLayerModel.setData()` 使用修改前的 `old_value` 发出该信号；空新描述仍不触发同步。

- [ ] **Step 5: 分类候选并询问一次**

`_sync_description()` 严格匹配三项地层条件，先收集空描述候选和 `old_description` 非空时与其完全相同的候选。只有后一类非空时调用：

```python
reply = QMessageBox.question(
    self,
    "同步岩性描述",
    f"发现 {len(same_description)} 处其他钻孔的相同地层描述仍为修改前内容。\n\n是否全部同步为新描述？",
    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
    QMessageBox.StandardButton.Yes,
)
```

`Yes` 合并两类候选，`No` 只处理空描述候选；其他非空描述永不覆盖。

- [ ] **Step 6: 运行交互测试确认 GREEN**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py -q`

Expected: all pass。

### Task 2: 锁定批量确认后的撤销重做

**Files:**
- Modify: `v3/tests/ui/test_description_sync.py`

- [ ] **Step 1: 写确认同步整体撤销重做测试**

确认同步空描述与相同旧描述后，第一次撤销同时恢复两个目标，源描述保留新值且源钻孔保持选中；重做同时恢复两个目标的新描述。

- [ ] **Step 2: 运行测试确认行为**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py -q`

Expected: all pass；如果失败，只修复候选合并与现有 `CompositeUndoAction` 的集成，不改通用撤销结构。

- [ ] **Step 3: 运行相关回归**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_description_sync.py tests/unit/test_undo_manager.py tests/ui/test_stability_behavior.py -q`

Expected: all pass。

### Task 3: 文档、全量验证与交付

**Files:**
- Modify: `v3/COMPATIBILITY.md`

- [ ] **Step 1: 更新兼容性报告**

记录空描述自动填充、相同旧描述确认更新、拒绝保护和整体撤销重做，并把 pytest 数量更新为实际值。

- [ ] **Step 2: 运行完整质量门槛**

```powershell
cd v3
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider -W error -o addopts='' -q
python -m ruff check src tests tools
python -m mypy src tools
python tools/hash_tree.py 'F:\钻孔数据工具\v2' --check v2-baseline.sha256
```

Expected: 全部 exit 0，v2 验证 124 个文件。

- [ ] **Step 3: 构建和冒烟 EXE**

Run: `cd v3; python -m PyInstaller --clean --noconfirm borehole_v3.spec`

Expected: 构建成功，窗口标题为“钻孔数据编辑工具 v3”，标准关闭消息后全部新进程退出。

- [ ] **Step 4: 提交、合并与清理**

提交源码、测试和报告，快进合并到 `main`；在合并后的 main 重跑质量门槛，复制已验证 EXE，并移除临时工作树和功能分支。
