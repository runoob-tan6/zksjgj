"""
钻孔数据编辑工具 - 文档字符串示例模块。

本模块展示了如何为Python代码添加规范的文档字符串。
采用Google风格的文档字符串格式。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ExampleDataClass:
    """示例数据类，展示数据类文档字符串写法。
    
    这个类用于演示如何为dataclass添加完整的文档字符串。
    包含类说明、属性说明和使用示例。
    
    Attributes:
        name: 数据名称，用于标识数据对象
        values: 数值列表，存储处理后的数据
        metadata: 元数据字典，存储附加信息
        is_valid: 数据有效性标志
        
    Example:
        >>> data = ExampleDataClass(name="测试数据", values=[1, 2, 3])
        >>> print(data.summary())
        '测试数据: 3个值'
    """

    name: str = ""
    values: list[float] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    is_valid: bool = True

    def summary(self) -> str:
        """生成数据摘要信息。
        
        返回一个简洁的字符串，包含数据名称和值的数量。
        
        Returns:
            格式化的摘要字符串，格式为 "名称: 数量个值"
            
        Example:
            >>> data = ExampleDataClass(name="测试", values=[1, 2])
            >>> data.summary()
            '测试: 2个值'
        """
        return f"{self.name}: {len(self.values)}个值"

    def validate(self) -> tuple[bool, list[str]]:
        """验证数据有效性。
        
        检查数据是否满足基本的有效性要求，包括：
        1. 名称不能为空
        2. 值列表不能为空
        3. 所有值必须为数字
        
        Returns:
            包含两个元素的元组：
            - bool: 验证是否通过
            - List[str]: 错误信息列表，验证通过时为空列表
            
        Raises:
            ValueError: 当数据格式严重错误时抛出
            
        Example:
            >>> data = ExampleDataClass(name="测试", values=[1, 2])
            >>> is_valid, errors = data.validate()
            >>> print(is_valid)
            True
        """
        errors: list[str] = []

        if not self.name:
            errors.append("名称不能为空")

        if not self.values:
            errors.append("值列表不能为空")

        for i, value in enumerate(self.values):
            if not isinstance(value, (int, float)):
                errors.append(f"第{i+1}个值不是数字: {value}")

        return len(errors) == 0, errors


def parse_example_file(file_path: Path, encoding: str = "utf-8") -> ExampleDataClass:
    """解析示例数据文件。
    
    读取指定格式的数据文件，解析其中的内容并返回数据对象。
    支持多种编码格式，自动检测文件编码。
    
    Args:
        file_path: 数据文件路径，必须是存在的文件
        encoding: 文件编码格式，默认为utf-8，支持gbk、ansi等
        
    Returns:
        解析后的ExampleDataClass对象，包含文件中的数据
        
    Raises:
        FileNotFoundError: 当指定的文件不存在时
        PermissionError: 当没有文件读取权限时
        UnicodeDecodeError: 当文件编码与指定编码不匹配时
        ValueError: 当文件格式不符合预期时
        
    Example:
        >>> from pathlib import Path
        >>> data = parse_example_file(Path("data.txt"))
        >>> print(data.name)
        '示例数据'
        
    Note:
        - 文件格式应为：第一行名称，后续每行一个数值
        - 空行会被自动忽略
        - 注释行（以#开头）会被跳过
    """
    if not file_path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")

    if not file_path.is_file():
        raise ValueError(f"路径不是文件: {file_path}")

    try:
        content = file_path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        # 尝试其他编码
        for alt_encoding in ["gbk", "ansi", "latin-1"]:
            try:
                content = file_path.read_text(encoding=alt_encoding)
                break
            except UnicodeDecodeError:
                continue
        else:
            raise UnicodeDecodeError(f"无法解码文件: {file_path}")

    lines = [line.strip() for line in content.splitlines() if line.strip()]

    if not lines:
        raise ValueError("文件为空")

    # 第一行作为名称
    name = lines[0]

    # 后续行解析为数值
    values: list[float] = []
    for i, line in enumerate(lines[1:], start=2):
        if line.startswith("#"):
            continue  # 跳过注释行

        try:
            value = float(line)
            values.append(value)
        except ValueError:
            raise ValueError(f"第{i}行不是有效数值: {line}")

    return ExampleDataClass(
        name=name,
        values=values,
        metadata={"source": str(file_path), "encoding": encoding}
    )


def process_batch_data(
    data_list: list[ExampleDataClass],
    filter_valid: bool = True,
    sort_by_name: bool = False
) -> list[ExampleDataClass]:
    """批量处理数据对象列表。
    
    对数据对象列表进行过滤、排序等批量处理操作。
    
    Args:
        data_list: 待处理的数据对象列表
        filter_valid: 是否只保留有效数据，默认为True
        sort_by_name: 是否按名称排序，默认为False
        
    Returns:
        处理后的数据对象列表
        
    Raises:
        TypeError: 当输入不是列表或包含非ExampleDataClass对象时
        
    Example:
        >>> data1 = ExampleDataClass(name="B", values=[1])
        >>> data2 = ExampleDataClass(name="A", values=[2])
        >>> result = process_batch_data([data1, data2], sort_by_name=True)
        >>> print(result[0].name)
        'A'
        
    Note:
        - 当filter_valid为True时，会调用每个对象的validate()方法
        - 排序是稳定的，相同名称的对象保持原始顺序
        - 此函数不会修改原始列表，返回新的列表
    """
    if not isinstance(data_list, list):
        raise TypeError(f"期望列表，得到{type(data_list)}")

    for i, item in enumerate(data_list):
        if not isinstance(item, ExampleDataClass):
            raise TypeError(f"第{i+1}个元素不是ExampleDataClass对象")

    # 创建副本避免修改原列表
    result = data_list.copy()

    # 过滤有效数据
    if filter_valid:
        result = [item for item in result if item.validate()[0]]

    # 排序
    if sort_by_name:
        result.sort(key=lambda x: x.name)

    return result


class DataProcessor:
    """数据处理器类，提供高级数据处理功能。
    
    这个类封装了复杂的数据处理逻辑，支持批量处理、
    数据验证、统计分析等功能。
    
    Attributes:
        batch_size: 批处理大小，默认为100
        enable_cache: 是否启用缓存，默认为True
        cache: 缓存字典，存储处理结果
        
    Example:
        >>> processor = DataProcessor(batch_size=50)
        >>> data = [ExampleDataClass(name=f"item{i}") for i in range(10)]
        >>> results = processor.process(data)
        >>> print(len(results))
        10
    """

    def __init__(self, batch_size: int = 100, enable_cache: bool = True) -> None:
        """初始化数据处理器。
        
        Args:
            batch_size: 批处理大小，必须大于0
            enable_cache: 是否启用缓存功能
            
        Raises:
            ValueError: 当batch_size小于等于0时
        """
        if batch_size <= 0:
            raise ValueError("batch_size必须大于0")

        self.batch_size = batch_size
        self.enable_cache = enable_cache
        self.cache: dict[str, ExampleDataClass] = {}
        self._process_count = 0

    def process(self, data_list: list[ExampleDataClass]) -> list[ExampleDataClass]:
        """处理数据列表。
        
        按批次处理数据列表，支持缓存和进度跟踪。
        
        Args:
            data_list: 待处理的数据列表
            
        Returns:
            处理后的数据列表
            
        Raises:
            ValueError: 当输入列表为空时
        """
        if not data_list:
            raise ValueError("数据列表不能为空")

        results: list[ExampleDataClass] = []

        # 分批处理
        for i in range(0, len(data_list), self.batch_size):
            batch = data_list[i:i + self.batch_size]
            batch_results = self._process_batch(batch)
            results.extend(batch_results)

            self._process_count += len(batch)

        return results

    def _process_batch(self, batch: list[ExampleDataClass]) -> list[ExampleDataClass]:
        """处理单个批次的数据。
        
        Args:
            batch: 当前批次的数据列表
            
        Returns:
            处理后的批次数据列表
        """
        results: list[ExampleDataClass] = []

        for item in batch:
            # 检查缓存
            cache_key = f"{item.name}_{len(item.values)}"
            if self.enable_cache and cache_key in self.cache:
                results.append(self.cache[cache_key])
                continue

            # 处理数据
            processed = self._process_item(item)
            results.append(processed)

            # 更新缓存
            if self.enable_cache:
                self.cache[cache_key] = processed

        return results

    def _process_item(self, item: ExampleDataClass) -> ExampleDataClass:
        """处理单个数据项。
        
        Args:
            item: 待处理的数据项
            
        Returns:
            处理后的数据项
        """
        # 示例处理逻辑：计算平均值并添加到元数据
        if item.values:
            avg = sum(item.values) / len(item.values)
            item.metadata["average"] = str(round(avg, 2))

        return item

    def get_statistics(self) -> dict[str, int]:
        """获取处理统计信息。
        
        Returns:
            包含统计信息的字典，包括：
            - processed_count: 已处理的数据项数量
            - cache_size: 缓存中的数据项数量
            - batch_size: 当前批处理大小
        """
        return {
            "processed_count": self._process_count,
            "cache_size": len(self.cache),
            "batch_size": self.batch_size,
        }
