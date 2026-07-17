# v3 剖面图与柱状图管理 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 v3 增加剖面文件组安全重命名，并自动生成、同步 ZK/NZK 柱状图清单文件。

**Architecture:** 新建应用层 `column_chart_service` 统一生成 `0yzk.-zkt` 和 `0nzk.-zkt`，加载、钻孔结构操作和保存前都调用该服务。`ProfileFile.old_name` 记录剖面最初磁盘前缀，现有 `SaveService` 在一个事务中写入新文件组并删除旧文件组；UI 只负责标签、输入校验和调用应用服务。

**Tech Stack:** Python 3.10+、PySide6、pytest、pytest-qt、Ruff、mypy、PyInstaller。

---

## 文件结构

```text
v3/src/borehole/
├── application/
│   ├── column_chart_service.py  # 柱状图规范内容与同步
│   ├── project_service.py       # 项目加载后同步
│   └── save_service.py          # 保存前同步、剖面重命名计划
├── domain/models.py             # ProfileFile.old_name
└── ui/main_window.py            # 树标签、右键重命名、操作后同步
v3/tests/
├── integration/
│   ├── test_column_charts.py
│   └── test_profile_rename.py
├── ui/test_profile_column_chart_ui.py
└── unit/test_column_chart_service.py
```

### Task 1: 实现柱状图规范内容服务

**Files:**
- Create: `v3/src/borehole/application/column_chart_service.py`
- Create: `v3/tests/unit/test_column_chart_service.py`
- Modify: `v3/src/borehole/application/project_service.py`
- Create: `v3/tests/integration/test_column_charts.py`

- [ ] **Step 1: 写分类、排序和缺失创建测试**

```python
def test_sync_creates_both_column_charts_with_natural_hole_order(tmp_path: Path) -> None:
    project = ProjectData(folder=tmp_path)
    for prefix in ("ZK10", "NZK2", "ZK2", "NZK1"):
        create_new_borehole(project, prefix)

    changed = synchronize_column_charts(project)

    assert changed == {"0yzk", "0nzk"}
    assert project.project_files["0yzk"].extra_files["zkt"] == "ZK2\nZK10\n★"
    assert project.project_files["0nzk"].extra_files["zkt"] == "NZK1\nNZK2\n★"
    assert project.project_files["0yzk"].modified
    assert project.project_files["0nzk"].modified
```

再覆盖空类型生成 `★`、内容相同时不标脏、其他 `project_files` 不被删除。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd v3; python -m pytest -p no:cacheprovider tests/unit/test_column_chart_service.py -q`

Expected: collection fails because `column_chart_service` does not exist.

- [ ] **Step 3: 实现同步服务**

```python
COLUMN_CHARTS = {
    "0yzk": HoleType.ZK,
    "0nzk": HoleType.NZK,
}


def render_column_chart(project: ProjectData, hole_type: HoleType) -> str:
    prefixes = [hole.prefix for hole in project.sorted_boreholes() if hole.hole_type == hole_type]
    return "\n".join([*prefixes, END_MARK])


def synchronize_column_charts(project: ProjectData) -> set[str]:
    folder = project.folder or Path.cwd()
    changed: set[str] = set()
    for name, hole_type in COLUMN_CHARTS.items():
        chart = project.project_files.get(name)
        if chart is None:
            chart = ProfileFile(name=name, path=folder / name)
            project.project_files[name] = chart
        expected = render_column_chart(project, hole_type)
        if chart.extra_files.get("zkt") != expected:
            chart.extra_files["zkt"] = expected
            chart.modified = True
            changed.add(name)
    return changed
```

- [ ] **Step 4: 写项目加载集成测试**

加载没有 `0yzk.-zkt`/`0nzk.-zkt` 的临时项目，断言两项进入模型和脏状态，但加载前后磁盘快照完全一致。加载已有正确内容的项目，断言不产生脏状态。

- [ ] **Step 5: 在 `load_project()` 完成钻孔装配后同步**

在返回 `ProjectData` 前调用 `synchronize_column_charts(project)`；不得在加载函数中调用保存服务或直接写文件。

- [ ] **Step 6: 运行单元和集成测试**

Run: `cd v3; python -m pytest -p no:cacheprovider tests/unit/test_column_chart_service.py tests/integration/test_column_charts.py -q`

Expected: all tests pass.

- [ ] **Step 7: 提交**

```powershell
git add v3/src/borehole/application/column_chart_service.py v3/src/borehole/application/project_service.py v3/tests
git commit -m "feat(v3): synchronize column chart files"
```

### Task 2: 将柱状图同步接入钻孔操作和保存

**Files:**
- Modify: `v3/src/borehole/ui/main_window.py`
- Modify: `v3/src/borehole/application/save_service.py`
- Modify: `v3/tests/integration/test_column_charts.py`
- Modify: `v3/tests/ui/test_profile_column_chart_ui.py`

- [ ] **Step 1: 写新增、复制、删除和改名同步测试**

使用 `MainWindow` 的现有操作服务或直接构造对应模型变化，分别断言操作后：

```python
assert project.project_files["0yzk"].extra_files["zkt"] == "ZK1\nZK3\n★"
assert project.project_files["0nzk"].extra_files["zkt"] == "NZK1\n★"
```

删除的钻孔不得继续出现在内容中；钻孔改名必须只保留新编号。

- [ ] **Step 2: 写保存前强制规范化测试**

```python
def test_save_service_canonicalizes_manually_changed_column_chart(tmp_path: Path) -> None:
    project = project_with_holes(tmp_path, "ZK1", "NZK1")
    synchronize_column_charts(project)
    project.project_files["0yzk"].extra_files["zkt"] = "错误内容"
    project.project_files["0yzk"].modified = True

    SaveService(project).save()

    assert (tmp_path / "0yzk.-zkt").read_text(encoding="utf-8") == "ZK1\n★"
```

断言 `0nzk.-zkt` 同时被创建，且现有编码/换行测试继续通过。

- [ ] **Step 3: 运行测试确认失败**

Run: `cd v3; python -m pytest -p no:cacheprovider tests/integration/test_column_charts.py -q`

Expected: FAIL because structural operations and `SaveService` do not resynchronize.

- [ ] **Step 4: 接入所有结构操作**

在 `_add_borehole()`、`_copy_borehole()`、`_delete_borehole()`、`_on_hole_id_changed()` 完成模型修改后调用 `synchronize_column_charts(self._project)`，再刷新树和摘要。不得直接写柱状图文件。

- [ ] **Step 5: 保存摘要和保存前同步**

`SaveService.summary()` 和 `SaveService.save()` 首行调用同步服务，保证缺失文件进入保存提示、执行保存时内容再次规范化。同步函数必须幂等，重复调用不得改变已正确模型。

- [ ] **Step 6: 运行相关回归**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/integration/test_column_charts.py tests/ui/test_profile_column_chart_ui.py tests/integration/test_save_service.py -q`

Expected: all tests pass.

- [ ] **Step 7: 提交**

```powershell
git add v3/src/borehole/application/save_service.py v3/src/borehole/ui/main_window.py v3/tests
git commit -m "feat(v3): keep column charts current"
```

### Task 3: 实现剖面文件组事务重命名

**Files:**
- Modify: `v3/src/borehole/domain/models.py`
- Modify: `v3/src/borehole/application/save_service.py`
- Create: `v3/tests/integration/test_profile_rename.py`

- [ ] **Step 1: 写四文件组重命名测试**

```python
def test_save_renames_complete_profile_group(tmp_path: Path) -> None:
    write_profile_group(tmp_path, "H8", {"d0": "d0", "g": "g", "k": "k"})
    project = load_project(tmp_path)
    profile = project.profile_files.pop("H8")
    profile.old_name = "H8"
    profile.name = "H9"
    profile.path = tmp_path / "H9"
    profile.modified = True
    project.profile_files["H9"] = profile

    SaveService(project).save()

    assert {path.name for path in tmp_path.iterdir() if path.is_file()} >= {"H9", "H9.-d0", "H9.-g", "H9.-k"}
    assert not any((tmp_path / name).exists() for name in ("H8", "H8.-d0", "H8.-g", "H8.-k"))
    assert profile.old_name is None
```

另覆盖连续 `H8 -> H9 -> H10` 仍删除 H8、事务失败恢复旧组且保留 `old_name`。

- [ ] **Step 2: 运行测试确认失败**

Run: `cd v3; python -m pytest -p no:cacheprovider tests/integration/test_profile_rename.py -q`

Expected: FAIL because `ProfileFile.old_name` and rename save plan are missing.

- [ ] **Step 3: 扩展领域模型**

```python
@dataclass
class ProfileFile:
    name: str
    path: Path
    content: str = ""
    extra_files: dict[str, str] = field(default_factory=dict)
    deleted_extra_files: set[str] = field(default_factory=set)
    modified: bool = False
    old_name: str | None = None
```

- [ ] **Step 4: 扩展保存计划**

对 `dirty_profiles` 先按新名称计划主文件和附属文件替换；当 `old_name` 与 `name` 不同时，把旧主文件和旧名称的全部 `extra_files` 后缀加入同一个事务的删除操作。不要把旧删除计入新文件数量两次。

保存成功后设置 `profile.old_name = None`；事务异常时 `_mark_saved()` 不执行，因此保留旧名称和脏状态。

- [ ] **Step 5: 运行集成和事务测试**

Run: `cd v3; python -m pytest -p no:cacheprovider tests/integration/test_profile_rename.py tests/integration/test_save_transaction.py tests/integration/test_save_service.py -q`

Expected: all tests pass.

- [ ] **Step 6: 提交**

```powershell
git add v3/src/borehole/domain/models.py v3/src/borehole/application/save_service.py v3/tests/integration
git commit -m "feat(v3): rename complete profile file groups"
```

### Task 4: 更新树标签和右键重命名交互

**Files:**
- Modify: `v3/src/borehole/ui/main_window.py`
- Modify: `v3/tests/characterization/test_ui_contract.py`
- Create: `v3/tests/ui/test_profile_column_chart_ui.py`

- [ ] **Step 1: 写树分组与菜单失败测试**

加载含 `H8` 的项目并刷新树，断言顶层分组包含“剖面图”和“柱状图”，不再包含旧分组名。选中 `profile:H8` 并构造右键菜单，断言命令顺序包含“复制剖面文件”“重命名剖面文件”“删除剖面文件”。

- [ ] **Step 2: 写有效、冲突和重复重命名测试**

模拟 `QInputDialog.getText()`：

- `H8 -> h9` 后模型键和名称为 `H9`，`old_name == "H8"`，树选中 `profile:H9`。
- `H9 -> H10` 后 `old_name` 仍为 `H8`。
- 输入非法名称、已存在模型名称、磁盘冲突文件时模型保持不变并调用警告框。

- [ ] **Step 3: 运行 UI 测试确认失败**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui/test_profile_column_chart_ui.py -q`

Expected: FAIL on old group labels and missing rename command.

- [ ] **Step 4: 实现 UI 变更**

把树节点和上下文匹配文字改为“剖面图”“柱状图”。新增 `_rename_profile(name: str)`：提交活动编辑器、读取输入、标准化大写、执行格式/模型/磁盘冲突检查，再更新 `ProfileFile` 和字典键；仅首次重命名设置 `old_name`。

磁盘冲突检查目标为新主文件及 `profile.extra_files` 的每个新前缀路径；允许目标路径等于本文件组当前旧路径。

- [ ] **Step 5: 更新保存确认文字和 UI 合同**

保存提示把“将保存项目配置文件”改为“将保存柱状图文件”。UI 合同继续断言原窗口尺寸、菜单和六标签页不变，只增加新树与上下文行为断言。

- [ ] **Step 6: 运行 UI 和视觉回归**

Run: `cd v3; $env:QT_QPA_PLATFORM='offscreen'; python -m pytest -p no:cacheprovider tests/ui tests/characterization -q`

Expected: all tests pass;空项目视觉截图因新增两个柱状图节点需要更新为“相同结构预期”而非与不自动生成的 v2 像素相等。视觉测试应使用未加载项目窗口，仍保持 v2/v3 像素一致。

- [ ] **Step 7: 提交**

```powershell
git add v3/src/borehole/ui/main_window.py v3/tests/ui v3/tests/characterization
git commit -m "feat(v3): expose profile rename and column chart groups"
```

### Task 5: 全量质量、文档和发布验收

**Files:**
- Modify: `v3/README.md`
- Modify: `v3/COMPATIBILITY.md`
- Modify: `v3/tests/test_release_packaging.py`

- [ ] **Step 1: 更新用户说明**

README 记录剖面图整体重命名、柱状图分类和保存时机；兼容报告记录 `H8` 四文件组、空清单 `★`、自然排序、回滚和 UI 合同证据。

- [ ] **Step 2: 运行全量质量门槛**

Run:

```powershell
cd v3
$env:QT_QPA_PLATFORM='offscreen'
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -p no:cacheprovider -W error -q
python -m ruff check src tests tools
python -m mypy src tools
python tools/hash_tree.py ..\v2 --check v2-baseline.sha256
```

Expected: all commands exit 0; pytest count is greater than 66; v2 verifies the same 124-file baseline.

- [ ] **Step 3: 构建 Windows EXE**

Run: `cd v3; python -m PyInstaller --clean --noconfirm borehole_v3.spec`

Expected: exit 0 and `v3/dist/钻孔数据编辑工具v3.exe` exists.

- [ ] **Step 4: EXE 启动冒烟**

启动单文件 EXE，查找 PyInstaller 子进程的窗口句柄，断言窗口标题为“钻孔数据编辑工具 v3”，发送标准关闭消息并确认窗口进程退出。

- [ ] **Step 5: 提交文档与发布测试**

```powershell
git add v3/README.md v3/COMPATIBILITY.md v3/tests/test_release_packaging.py
git commit -m "docs(v3): document profile and column chart workflows"
```

- [ ] **Step 6: 最终差异审查**

Run: `git diff --check main...HEAD; git status --short; git log --oneline main..HEAD`

Expected: 产品改动仅位于 `v3/`，规格和计划位于 `docs/superpowers/`，v2 没有修改。
