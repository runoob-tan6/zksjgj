# 钻孔数据编辑工具

用于水利勘察项目钻孔数据管理的桌面编辑工具。

## 功能

- 加载和解析 ZK、NZK 钻孔数据文件
- 编辑主文件、基础数据和试验数据
- 校验钻孔数据完整性
- 生成钻孔数据文件
- 导出地层试验汇总表

## 开发环境

项目基于 Python 3.10+。

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## 运行

```powershell
python app.py
```

## 打包

需要打包 exe 时运行：

```powershell
.\打包exe.bat
```

## 说明

仓库只保存源码、测试和开发文档。本地配置、构建产物、exe 文件以及实际项目钻孔数据不纳入版本管理。
