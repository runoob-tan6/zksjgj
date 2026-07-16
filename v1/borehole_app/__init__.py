"""钻孔数据编辑工具 - borehole_app 包。

本包实现了钻孔数据编辑工具的核心功能，包括：

模块说明：
    - models: 数据模型定义
    - parser: 文件解析
    - writer: 文件写入
    - validation: 数据校验
    - project: 项目管理
    - undo: 撤销/重做
    - settings: 应用设置
    - ui_main: 主窗口
    - ui_main_file: 主文件编辑页
    - ui_basic_data: 基础数据编辑页
    - ui_test_data: 试验数据编辑页
    - ui_raw_text: 原始文本显示页
    - ui_tree_helpers: Treeview公共逻辑

典型用法：
    >>> from borehole_app.project import load_project
    >>> from borehole_app.ui_main import main
    >>> main()
"""
