"""
钻孔数据编辑工具 - pytest配置文件。

本文件包含pytest的配置和共享fixtures。
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_path(tmp_path: Path) -> Path:
    """提供临时目录路径。
    
    这是pytest内置fixture的包装，确保每个测试都有独立的临时目录。
    
    Args:
        tmp_path: pytest提供的临时目录路径
        
    Returns:
        临时目录的Path对象
    """
    return tmp_path


@pytest.fixture
def sample_borehole_data() -> dict[str, str]:
    """提供示例钻孔数据。
    
    Returns:
        包含示例钻孔数据的字典
    """
    return {
        "main": "ZK1\n10.5\n100.0\n测试地点\n90,90\n1000\n2024-01-01\n测试项目\n001\n初步勘察\n0,0\n2024-01-02\n10.0\nL\n90,90\n测试单位\n★\n",
        "c": "5,A\n10,B\n15,C\n★\n",
        "b": "5,Q\n10,D\n15,N\n★\n",
        "g": "5,1\n10,2\n15,3\n★\n",
        "h": "#5\n强风化花岗岩\n#10\n中风化花岗岩\n#15\n微风化花岗岩\n★\n",
        "o": "1,5,S1\n6,10,S2\n11,15,S3\n★\n",
        "q": "1,5,10\n6,10,15\n11,15,20\n★\n",
    }


@pytest.fixture
def sample_project_folder(tmp_path: Path, sample_borehole_data: dict[str, str]) -> Path:
    """创建示例项目文件夹。
    
    Args:
        tmp_path: 临时目录路径
        sample_borehole_data: 示例钻孔数据
        
    Returns:
        包含示例数据的项目文件夹路径
    """
    project_folder = tmp_path / "test_project"
    project_folder.mkdir()

    # 创建钻孔文件夹
    borehole_folder = project_folder / "ZK1"
    borehole_folder.mkdir()

    # 写入数据文件
    for suffix, content in sample_borehole_data.items():
        if suffix == "main":
            file_path = borehole_folder / "ZK1"
        else:
            file_path = borehole_folder / f"ZK1.-{suffix}"

        file_path.write_text(content, encoding="utf-8")

    return project_folder


@pytest.fixture
def gbk_encoded_folder(tmp_path: Path) -> Path:
    """创建GBK编码的测试文件夹。
    
    Args:
        tmp_path: 临时目录路径
        
    Returns:
        包含GBK编码文件的文件夹路径
    """
    folder = tmp_path / "gbk_project"
    folder.mkdir()

    # 创建GBK编码的主文件
    main_file = folder / "ZK1"
    main_file.write_text("ZK1\n10\n测试地点\n★\n", encoding="gbk")

    # 创建GBK编码的c文件
    c_file = folder / "ZK1.-c"
    c_file.write_text("5,A\n10,B\n★\n", encoding="gbk")

    return folder


@pytest.fixture
def empty_project_folder(tmp_path: Path) -> Path:
    """创建空项目文件夹。
    
    Args:
        tmp_path: 临时目录路径
        
    Returns:
        空项目文件夹路径
    """
    folder = tmp_path / "empty_project"
    folder.mkdir()
    return folder


@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """提供测试数据目录路径。
    
    Returns:
        测试数据目录的Path对象
    """
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def mock_borehole():
    """提供模拟的Borehole对象。
    
    Returns:
        模拟的Borehole对象
    """
    from borehole_app.models import BasicLayer, Borehole, MainFileData, TestRecord

    borehole = Borehole(
        prefix="ZK_TEST",
        folder=Path("/tmp/test"),
        hole_type="ZK"
    )

    borehole.main = MainFileData(lines=["ZK_TEST", "10"] + [""] * 14)
    borehole.layers = [
        BasicLayer(bottom_depth="5", lithology_code="A"),
        BasicLayer(bottom_depth="10", lithology_code="B"),
    ]
    borehole.tests["o"] = [
        TestRecord(values=["1", "5", "S1"]),
        TestRecord(values=["6", "10", "S2"]),
    ]

    return borehole


class MockTkinterApp:
    """模拟Tkinter应用程序，用于UI测试。"""

    def __init__(self):
        self.title = "测试应用"
        self.geometry_val = "800x600"
        self.destroyed = False

    def title(self, title: str) -> None:
        self.title = title

    def geometry(self, geometry: str) -> None:
        self.geometry_val = geometry

    def destroy(self) -> None:
        self.destroyed = True

    def mainloop(self) -> None:
        pass


@pytest.fixture
def mock_tkinter_app():
    """提供模拟的Tkinter应用程序。
    
    Returns:
        模拟的Tkinter应用程序对象
    """
    return MockTkinterApp()


def pytest_configure(config):
    """pytest配置钩子。
    
    Args:
        config: pytest配置对象
    """
    # 添加自定义标记
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "ui: marks tests that require UI (deselect with '-m \"not ui\"')"
    )
    config.addinivalue_line(
        "markers", "integration: marks integration tests"
    )


def pytest_collection_modifyitems(config, items):
    """修改测试项目集合。
    
    Args:
        config: pytest配置对象
        items: 测试项目列表
    """
    # 自动为慢速测试添加标记
    for item in items:
        if "slow" in item.nodeid:
            item.add_marker(pytest.mark.slow)

        # 为UI测试添加标记
        if "ui" in item.nodeid:
            item.add_marker(pytest.mark.ui)
