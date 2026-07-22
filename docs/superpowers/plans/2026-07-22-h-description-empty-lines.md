# v3 `.-h` 描述空行修复 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 生成 `.-h` 文件时忽略不完整描述记录，保证文件中没有空描述行。

**Architecture:** 只调整 `render_h_file()` 的序列化条件，不修改通用文本生成器和旧文件解析器。以渲染单元测试锁定格式，以保存服务集成测试锁定磁盘结果。

**Tech Stack:** Python 3.10+、pytest、Ruff、mypy、PyInstaller。

---

### Task 1: 用测试复现空行

**Files:**
- Create: `v3/tests/unit/test_file_writer.py`
- Modify: `v3/tests/integration/test_save_service.py`

- [ ] **Step 1: 添加渲染测试**

构造带空描述、纯空白描述和完整描述的 `Borehole`，断言只输出完整记录，值去除首尾空白；没有完整记录时只输出 `★`。

- [ ] **Step 2: 添加保存集成测试**

加载兼容项目，把其中一层描述置空并保存 `h`，断言磁盘内容不含空行或该层的孤立深度。

- [ ] **Step 3: 运行测试确认 RED**

Run: `cd v3; python -m pytest tests/unit/test_file_writer.py tests/integration/test_save_service.py -q`

Expected: 新测试失败，当前实现会输出空描述行和孤立深度。

### Task 2: 最小修复序列化逻辑

**Files:**
- Modify: `v3/src/borehole/infrastructure/file_writer.py`

- [ ] **Step 1: 规范化并过滤记录**

在 `render_h_file()` 中分别对深度和描述执行 `str(value or "").strip()`，只有二者均非空时才追加两行。

- [ ] **Step 2: 运行目标测试确认 GREEN**

Run: `cd v3; python -m pytest tests/unit/test_file_writer.py tests/integration/test_save_service.py -q`

Expected: all pass。

### Task 3: 文档和完整交付验证

**Files:**
- Modify: `v3/COMPATIBILITY.md`

- [ ] **Step 1: 更新兼容性报告**

记录 `.-h` 不完整描述过滤行为并更新实际 pytest 数量。

- [ ] **Step 2: 运行完整质量门槛**

Run: pytest `-W error`、Ruff、mypy、v2 哈希检查。

Expected: 全部 exit 0，v2 清单 124 个文件一致。

- [ ] **Step 3: 构建和冒烟 EXE**

Run: PyInstaller 构建并启动发布 EXE，确认 v3 窗口标题和正常关闭。

Expected: 构建成功，进程正常退出。
