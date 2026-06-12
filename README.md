# 钻孔数据编辑工具

用于水利勘察项目的钻孔数据桌面编辑工具，支持 ZK、NZK 钻孔数据的加载、编辑、校验、生成和试验汇总导出。

## 功能

- 加载和解析 ZK、NZK 钻孔数据文件
- 编辑主文件、基础数据和试验数据
- 校验钻孔数据完整性
- 生成新增或已修改的钻孔数据文件
- 导出地层试验汇总表

## 项目结构

```text
.
├── app.py                      # 应用入口
├── borehole_app/               # 桌面应用源码
│   ├── models.py               # 核心数据模型
│   ├── parser.py               # 钻孔文件解析
│   ├── project.py              # 项目加载和钻孔管理
│   ├── writer.py               # 文件生成、备份和导出
│   ├── validation.py           # 数据校验
│   └── ui_*.py                 # Tkinter 界面模块
├── tests/                      # 自动化测试
├── docs/
│   ├── reports/                # 代码审查、优化报告和行动清单
│   └── examples/               # 示例模板
├── pyproject.toml              # 项目元数据、pytest、coverage、mypy 配置
├── ruff.toml                   # Ruff lint/format 配置
└── 钻孔数据编辑工具.spec        # PyInstaller 打包配置
```

## 开发环境

项目基于 Python 3.10+。

```powershell
python -m pip install -e ".[dev]"
```

## 运行

```powershell
python app.py
```

## 测试和质量检查

日常测试：

```powershell
python -m pytest
python run_regression_tests.py
```

代码检查和格式化：

```powershell
python -m ruff check .
python -m ruff format .
```

需要查看覆盖率时：

```powershell
python -m pytest --cov=borehole_app --cov-report=term-missing --cov-report=html:coverage
```

## 打包

需要打包 exe 时运行：

```powershell
.\打包exe.bat
```

## 版本管理说明

仓库只保存源码、测试、开发文档和项目配置。本地配置、构建产物、exe 文件、缓存和实际项目钻孔数据不纳入版本管理。
