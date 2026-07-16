# 钻孔数据编辑工具 v3 兼容重构 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从 v2 建立 UI 和正常操作行为完全兼容的独立 v3，并改善内部结构、性能、稳定性和测试覆盖。

**Architecture:** 完整复制 v2 的源码结构并保留 `borehole` 包名和现有 Qt 控件树；先用特征测试冻结行为，再把后台任务和事务保存从 `MainWindow` 抽离到应用/基础设施模块。所有可见差异仅限 v3 版本标识，明确缺陷通过测试驱动方式修复。

**Tech Stack:** Python 3.10+、PySide6、openpyxl、pytest、pytest-qt、Ruff、mypy、PyInstaller。

---

## 文件结构

```text
v3/
├── assets/                         # v2 使用的同一组应用图标
├── src/borehole/
│   ├── application/
│   │   ├── project_service.py     # 保留 v2 项目用例
│   │   ├── save_service.py        # 保存计划和结果
│   │   ├── task_runner.py         # 后台任务生命周期
│   │   └── undo_manager.py        # 保留撤销语义
│   ├── domain/                    # 保留 v2 模型、枚举和校验语义
│   ├── infrastructure/
│   │   ├── file_parser.py         # 保留格式解析
│   │   ├── file_writer.py         # 保留格式渲染
│   │   ├── save_transaction.py    # 临时写入、备份、提交和回滚
│   │   ├── table_importer.py
│   │   └── xlsx_export.py
│   └── ui/                        # 保留 v2 控件树、文字和交互入口
├── tests/
│   ├── characterization/          # v2/v3 功能、UI 和文件对照
│   ├── integration/
│   ├── ui/
│   └── unit/
├── tools/hash_tree.py
├── README.md
├── borehole_v3.spec
├── build_exe.bat
├── pyproject.toml
├── run.py
└── v2-baseline.sha256
```

### Task 1: 建立隔离工作树和 v3 原样副本

**Files:**
- Create: `.worktrees/v3-compatible/`
- Copy: `v2/src/` to `.worktrees/v3-compatible/v3/src/`
- Copy: `v2/tests/` to `.worktrees/v3-compatible/v3/tests/`
- Create: `.worktrees/v3-compatible/v3/tools/hash_tree.py`
- Create: `.worktrees/v3-compatible/v3/v2-baseline.sha256`
- Modify: `.worktrees/v3-compatible/v3/pyproject.toml`
- Modify: `.worktrees/v3-compatible/v3/run.py`
- Create: `.worktrees/v3-compatible/v3/README.md`

- [ ] **Step 1: 创建不覆盖旧 v3 的分支和工作树**

Run: `git worktree add .worktrees/v3-compatible -b codex/v3-compatible main`

Expected: 新工作树位于 `.worktrees/v3-compatible`，旧 `codex/v3-refactor` 工作树仍存在。

- [ ] **Step 2: 复制 v2 的项目文件，排除缓存和构建产物**

复制 `src`、`tests`、`pyproject.toml`、`run.py`、两个 spec 和打包脚本。删除副本中的 `__pycache__`、`.pytest_cache`、`.mypy_cache`、`.ruff_cache`、`build` 和 `dist`。复制根目录 `assets/app_icon.*` 到 `v3/assets/`。

- [ ] **Step 3: 写哈希工具测试并确认失败**

```python
# v3/tests/unit/test_hash_tree.py
from pathlib import Path

from tools.hash_tree import hash_tree


def test_hash_tree_is_stable_and_ignores_directories(tmp_path: Path) -> None:
    (tmp_path / "b").write_bytes(b"b")
    (tmp_path / "folder").mkdir()
    (tmp_path / "folder" / "a").write_bytes(b"a")

    rows = hash_tree(tmp_path)

    assert [row.path for row in rows] == ["b", "folder/a"]
    assert all(len(row.sha256) == 64 for row in rows)
```

Run: `cd v3; python -m pytest -p no:cacheprovider tests/unit/test_hash_tree.py -q`

Expected: FAIL because `tools.hash_tree` does not exist.

- [ ] **Step 4: 实现哈希工具并生成基线**

```python
# v3/tools/hash_tree.py
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class HashRow:
    sha256: str
    size: int
    path: str


def hash_tree(root: Path) -> list[HashRow]:
    return [
        HashRow(hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_size, path.relative_to(root).as_posix())
        for path in sorted(item for item in root.rglob("*") if item.is_file())
    ]
```

命令行支持 `python tools/hash_tree.py <root>` 输出清单，以及 `python tools/hash_tree.py <root> --check <manifest>` 比较清单并以非零状态报告差异。清单每行格式为 `<sha256>  <size>  <relative-path>`，输入固定为主工作区 `v2/`。

- [ ] **Step 5: 更新版本标识但不动 UI 结构**

把项目名改为 `borehole-editor-v3`、版本改为 `3.0.0`、脚本名改为 `borehole-v3`；窗口标题改为 `钻孔数据编辑工具 v3`。其余字符串和布局保持不变。

- [ ] **Step 6: 运行复制基线**

Run: `cd v3; python -m pytest -p no:cacheprovider -q`

Expected: 31 tests pass; no source file is imported from `v2`.

- [ ] **Step 7: 提交**

```powershell
git add v3
git commit -m "chore(v3): copy compatible v2 baseline"
```

### Task 2: 冻结功能入口和 UI 结构

**Files:**
- Create: `v3/tests/characterization/test_ui_contract.py`
- Create: `v3/tests/characterization/test_source_inventory.py`
- Create: `v3/tests/ui/conftest.py`

- [ ] **Step 1: 写 UI 合同测试**

```python
def test_main_window_preserves_v2_navigation(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.windowTitle() == "钻孔数据编辑工具 v3"
    assert [action.text() for action in window.menuBar().actions()] == ["文件(&F)", "编辑(&E)", "工具(&T)"]
    assert [window._tabs.tabText(index) for index in range(window._tabs.count())] == [
        "基本信息", "试验数据", "标贯分析", "数据文件", "原始文本", "校验结果"
    ]
    assert window.minimumSize().width() == 980
    assert window.minimumSize().height() == 640
    assert window.size().width() == 1180
    assert window.size().height() == 760
```

另断言全部菜单项、快捷键、主分栏类型、树控件、摘要标签和状态栏控件与 v2 清单一致。

- [ ] **Step 2: 运行测试确认待补断言失败**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/characterization/test_ui_contract.py -q`

Expected: FAIL on incomplete version/menu shortcut or object inventory.

- [ ] **Step 3: 只修正版本配置和测试可访问性**

不得改变 `_build_menu()`、`_build_ui()` 的控件创建顺序、布局参数、文字和信号连接。若测试需要访问控件，使用现有属性或 Qt 子对象查询，不向生产 UI 添加测试专用 API。

- [ ] **Step 4: 写源码功能清单测试**

验证 v3 包含 v2 的所有 Python 模块、MainWindow 用户命令方法、页面类和基础设施公开函数；允许新增模块，不允许基线符号缺失。

- [ ] **Step 5: 运行 UI 合同测试和全量回归**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/characterization tests/unit -q`

Expected: all tests pass.

- [ ] **Step 6: 提交**

```powershell
git add v3/tests
git commit -m "test(v3): freeze v2 UI and feature contract"
```

### Task 3: 扩充文件格式和导入导出回归

**Files:**
- Create: `v3/tests/fixtures/legacy_project/*`
- Create: `v3/tests/integration/test_project_roundtrip.py`
- Create: `v3/tests/integration/test_table_importer.py`
- Create: `v3/tests/integration/test_xlsx_export.py`
- Modify: `v3/src/borehole/infrastructure/file_parser.py`
- Modify: `v3/src/borehole/infrastructure/file_writer.py`
- Modify: `v3/src/borehole/infrastructure/table_importer.py`
- Modify: `v3/src/borehole/infrastructure/xlsx_export.py`

- [ ] **Step 1: 建立 UTF-8/LF 与 GBK/CRLF 合成项目**

固定样本覆盖 ZK/NZK 主文件、`.-b/c/d/g/h/e/f/l/m/n/o/q`、未知附属文件、剖面主文件/附属文件和 `0` 开头配置文件。样本不得包含真实项目隐私数据。

- [ ] **Step 2: 写只读和往返测试**

```python
def test_loading_project_does_not_change_any_bytes(project_copy: Path) -> None:
    before = snapshot_bytes(project_copy)
    load_project(project_copy)
    assert snapshot_bytes(project_copy) == before


def test_unchanged_documents_render_like_v2(project_copy: Path) -> None:
    project = load_project(project_copy)
    generated = render_project_without_writing(project)
    assert generated == expected_v2_outputs(project_copy)
```

- [ ] **Step 3: 运行测试确认覆盖缺口**

Run: `cd v3; python -m pytest tests/integration/test_project_roundtrip.py -q`

Expected: tests expose unsupported encoding/newline metadata or missing fixtures before implementation.

- [ ] **Step 4: 最小化修复解析/输出边界**

保留 v2 字段顺序、结束标记、空值和文件名规则。明确处理 UTF-8、UTF-8 BOM、GBK、LF 和 CRLF；未知附属文件不经解析重写。

- [ ] **Step 5: 写非有限数字导入导出失败测试**

```python
@pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-inf"])
def test_import_rejects_non_finite_depth(value: str, table_path: Path) -> None:
    write_depth(table_path, value)
    with pytest.raises(ValueError, match="有限数字"):
        import_from_table(table_path, table_path.parent / "out")
```

- [ ] **Step 6: 实现有限数校验并跑全量测试**

所有字符串到浮点数的入口使用 `math.isfinite()`；正常数值格式与 v2 相同。

Run: `cd v3; python -m pytest tests/integration tests/unit -q`

Expected: all tests pass.

- [ ] **Step 7: 提交**

```powershell
git add v3/src/borehole/infrastructure v3/tests
git commit -m "test(v3): lock legacy file compatibility"
```

### Task 4: 实现可回滚保存事务

**Files:**
- Create: `v3/src/borehole/infrastructure/save_transaction.py`
- Create: `v3/tests/integration/test_save_transaction.py`
- Create: `v3/src/borehole/application/save_service.py`
- Create: `v3/tests/unit/test_save_service.py`
- Modify: `v3/src/borehole/ui/main_window.py`

- [ ] **Step 1: 写保存事务失败测试**

```python
def test_commit_failure_restores_replaced_files(tmp_path: Path, failing_replace) -> None:
    target = tmp_path / "ZK1"
    target.write_text("old", encoding="utf-8")
    transaction = SaveTransaction(tmp_path)
    transaction.replace(target, b"new")
    failing_replace.fail_on_call(2)

    with pytest.raises(SaveTransactionError):
        transaction.commit()

    assert target.read_text(encoding="utf-8") == "old"
    assert not list(tmp_path.glob(".borehole-v3-*.tmp"))
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd v3; python -m pytest tests/integration/test_save_transaction.py -q`

Expected: FAIL because transaction module is missing.

- [ ] **Step 3: 实现同目录临时文件、备份、原子提交和逆序回滚**

`SaveTransaction` 接收替换和删除操作。`commit()` 必须先完成全部临时写入，再备份全部目标，最后提交；任一提交失败时按逆序恢复。清理失败作为附加诊断，不覆盖原始错误。

- [ ] **Step 4: 写保存计划测试**

测试钻孔、剖面、剖面附属文件、项目配置文件、删除项和当前编辑器刷新都进入与 v2 相同的保存集合；成功才清除脏状态，失败保留。

- [ ] **Step 5: 实现 SaveService 并接回原 UI 槽**

`MainWindow._save_data()` 仍显示原确认框并启动后台任务；`_finish_save()` 仍显示原提示并恢复原选择。仅把保存集合生成和磁盘提交委托给 `SaveService`。

- [ ] **Step 6: 运行保存、UI 和全量回归**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/unit/test_save_service.py tests/integration/test_save_transaction.py tests/characterization/test_ui_contract.py -q`

Expected: all tests pass.

- [ ] **Step 7: 提交**

```powershell
git add v3/src/borehole/application/save_service.py v3/src/borehole/infrastructure/save_transaction.py v3/src/borehole/ui/main_window.py v3/tests
git commit -m "refactor(v3): make project saves transactional"
```

### Task 5: 抽离后台任务生命周期并修复线程清理

**Files:**
- Create: `v3/src/borehole/application/task_runner.py`
- Create: `v3/tests/unit/test_task_runner.py`
- Create: `v3/tests/ui/test_background_tasks.py`
- Modify: `v3/src/borehole/ui/main_window.py`

- [ ] **Step 1: 写成功、失败和重复启动测试**

```python
def test_failed_task_reenables_window_actions(qtbot, window, failing_task) -> None:
    window._start_task(failing_task)
    qtbot.waitUntil(lambda: window._worker is None)

    assert all(action.isEnabled() for action in window.menuBar().actions())
    assert window.statusBar().currentMessage() != "正在处理..."
```

另覆盖同一时间拒绝冲突任务、成功回调抛错、关闭时等待线程和对象只清理一次。

- [ ] **Step 2: 运行测试确认现有生命周期缺陷**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/ui/test_background_tasks.py -q`

Expected: at least one test fails because v2 worker is defined in `main_window.py` and cleanup logic is distributed across callbacks.

- [ ] **Step 3: 实现 TaskRunner**

任务对象发出 `succeeded(object)`、`failed(str)` 和 `finished()`；`TaskRunner` 集中设置忙碌状态、持有线程引用、调用回调并在所有路径恢复状态。

- [ ] **Step 4: 保留原入口接入加载、保存、导入和导出**

不得更改菜单动作、对话框文字、状态栏文字和回调顺序。`MainWindow` 的 `_load_project_path()`、`_save_data()`、`_import_table_file()`、`_export_layer_tests()` 只替换内部线程启动代码。

- [ ] **Step 5: 运行 UI 对照和全量回归**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/ui tests/characterization -q`

Expected: all tests pass and no `QThread: Destroyed while thread is still running` warning.

- [ ] **Step 6: 提交**

```powershell
git add v3/src/borehole/application/task_runner.py v3/src/borehole/ui/main_window.py v3/tests
git commit -m "refactor(v3): centralize background task cleanup"
```

### Task 6: 优化项目刷新和数据处理热点

**Files:**
- Create: `v3/tests/unit/test_performance_regressions.py`
- Create: `v3/tests/ui/test_refresh_behavior.py`
- Modify: `v3/src/borehole/domain/models.py`
- Modify: `v3/src/borehole/ui/main_window.py`
- Modify: `v3/src/borehole/infrastructure/xlsx_export.py`

- [ ] **Step 1: 写调用次数和结果一致性测试**

测试一次字段编辑不触发完整项目重载；一次树刷新只执行一次钻孔自然排序；大项目导出不重复计算相同分层分组；切换节点前活动编辑器只提交一次。

- [ ] **Step 2: 运行测试确认重复工作**

Run: `cd v3; python -m pytest tests/unit/test_performance_regressions.py tests/ui/test_refresh_behavior.py -q`

Expected: FAIL on excessive call counts while produced values remain correct.

- [ ] **Step 3: 实现局部缓存和批量刷新**

缓存只存在于单次操作范围内，不在领域对象上保存易失派生状态。使用 Qt 信号阻断器避免加载时回写；树刷新提前保存并恢复选择；导出循环预计算分组和样式。

- [ ] **Step 4: 验证输出与 UI 合同不变**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest tests/unit/test_performance_regressions.py tests/ui/test_refresh_behavior.py tests/characterization -q`

Expected: all tests pass.

- [ ] **Step 5: 提交**

```powershell
git add v3/src v3/tests
git commit -m "perf(v3): reduce redundant refresh and export work"
```

### Task 7: 静态质量、视觉对照和兼容报告

**Files:**
- Modify: `v3/pyproject.toml`
- Modify: `v3/src/**/*.py`
- Modify: `v3/tests/**/*.py`
- Create: `v3/tests/characterization/test_visual_contract.py`
- Create: `v3/COMPATIBILITY.md`

- [ ] **Step 1: 消除 pytest 收集警告**

测试中用别名导入领域 `TestRecord`（例如 `TestRecord as Record`），不得改领域类名或 UI 显示名。

- [ ] **Step 2: 运行 Ruff 和 mypy 获取真实失败清单**

Run: `cd v3; python -m ruff check src tests tools; python -m mypy src tools`

Expected: record current failures before changing source.

- [ ] **Step 3: 最小化修复静态问题**

修复未使用导入、过时类型语法、未标注函数和明确的可空类型问题。不得批量重排 UI 构造代码，不得改变控件文字和信号顺序。

- [ ] **Step 4: 写固定页面视觉对照测试**

用固定字体、窗口尺寸和合成数据渲染基本信息、试验数据、标贯分析、数据文件、原始文本和校验结果。测试遮盖标题栏版本标识后比较 v2/v3 图像尺寸和像素差异阈值，并输出差异图供人工复核。

- [ ] **Step 5: 编写兼容报告**

逐项记录功能清单、自动化测试、视觉对照、已修复缺陷、文件格式样本、性能基线和尚存风险。不得留下占位符或未验证结论。

- [ ] **Step 6: 运行完整质量门槛**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider -q; python -m ruff check src tests tools; python -m mypy src tools`

Expected: all commands exit 0 with no warnings.

- [ ] **Step 7: 提交**

```powershell
git add v3
git commit -m "quality(v3): complete compatibility verification"
```

### Task 8: 打包、启动冒烟和 v2 完整性验收

**Files:**
- Create: `v3/borehole_v3.spec`
- Create: `v3/build_exe.bat`
- Create: `v3/tests/test_release_packaging.py`
- Modify: `v3/README.md`

- [ ] **Step 1: 写发布配置测试并确认失败**

```python
def test_release_files_use_v3_identity() -> None:
    assert 'name="钻孔数据编辑工具v3"' in Path("borehole_v3.spec").read_text(encoding="utf-8")
    assert "borehole-editor-v3" in Path("pyproject.toml").read_text(encoding="utf-8")
```

Run: `cd v3; python -m pytest tests/test_release_packaging.py -q`

Expected: FAIL until v3 spec and script exist.

- [ ] **Step 2: 创建 v3 打包配置和 README**

PyInstaller 入口使用 `run.py`，包含 `assets` 和必要 Qt/openpyxl 资源，EXE 名为 `钻孔数据编辑工具v3.exe`。README 记录运行、测试、质量检查、打包、兼容边界和 v2 不可修改约束。

- [ ] **Step 3: 构建 EXE**

Run: `cd v3; python -m PyInstaller --clean --noconfirm borehole_v3.spec`

Expected: exit 0 and `dist/钻孔数据编辑工具v3.exe` exists.

- [ ] **Step 4: 启动冒烟**

启动 EXE，等待主窗口出现，验证标题为 v3、菜单和标签页合同一致，然后正常关闭；进程退出码为 0，不存在立即崩溃或线程警告。

- [ ] **Step 5: 最终全量验证**

Run:

```powershell
cd v3
$env:QT_QPA_PLATFORM='offscreen'
python -m pytest -p no:cacheprovider -q
python -m ruff check src tests tools
python -m mypy src tools
python tools/hash_tree.py ../../v2 --check v2-baseline.sha256
git status --short -- ../../v2
```

Expected: pytest、Ruff、mypy 和哈希检查全部 exit 0；`v2/` 没有新增、修改或删除文件。

- [ ] **Step 6: 提交发布配置**

```powershell
git add v3/borehole_v3.spec v3/build_exe.bat v3/README.md v3/tests/test_release_packaging.py
git commit -m "build(v3): package compatible desktop release"
```

- [ ] **Step 7: 最终复核分支差异**

Run: `git diff --stat main...HEAD; git log --oneline --decorate main..HEAD`

Expected: 所有产品改动仅位于 `v3/`，文档位于 `docs/superpowers/`，`v2/` 无差异。
