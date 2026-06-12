"""钻孔数据编辑工具 - 撤销/重做模块。

本模块实现了基于快照的撤销/重做系统，包括：
- 钻孔数据快照捕获和恢复
- 撤销/重做操作管理
- 快照内容比较

典型用法：
    >>> from borehole_app.undo import UndoManager, BoreholeSnapshot
    >>> manager = UndoManager()
    >>> snapshot = BoreholeSnapshot.capture(borehole)
    >>> # 执行修改...
    >>> manager.push(UndoAction(borehole, "修改深度", snapshot, new_snapshot))
    >>> if manager.can_undo():
    ...     action = manager.pop_undo()
    ...     action.before.restore(borehole)
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import BasicLayer, Borehole, TestRecord


def copy_layers(layers: list[BasicLayer]) -> list[BasicLayer]:
    """复制地层列表，创建独立副本。

    Args:
        layers: 地层列表

    Returns:
        地层列表的独立副本
    """
    return [
        BasicLayer(
            bottom_depth=layer.bottom_depth,
            lithology_code=layer.lithology_code,
            formation=layer.formation,
            structure=layer.structure,
            weathering=layer.weathering,
            description=layer.description,
        )
        for layer in layers
    ]


def copy_tests(tests: dict[str, list[TestRecord]]) -> dict[str, list[TestRecord]]:
    """复制试验数据字典，创建独立副本。

    Args:
        tests: 试验数据字典

    Returns:
        试验数据字典的独立副本
    """
    return {suffix: [TestRecord(values=list(record.values)) for record in records] for suffix, records in tests.items()}


@dataclass
class BoreholeSnapshot:
    """钻孔数据快照类。

    存储钻孔在某一时刻的完整状态，用于撤销/重做操作。

    Attributes:
        prefix: 钻孔编号
        hole_type: 钻孔类型
        main_lines: 主文件内容
        layers: 地层列表
        tests: 试验数据
        dirty: 是否有修改
        dirty_suffixes: 有修改的后缀集合
        is_new: 是否为新建
        old_prefix: 编号变更前的旧前缀

    Example:
        >>> snapshot = BoreholeSnapshot.capture(borehole)
        >>> # 执行修改...
        >>> borehole.layers[0].bottom_depth = "10"
        >>> # 恢复到快照状态
        >>> snapshot.restore(borehole)
    """

    prefix: str
    hole_type: str
    main_lines: list[str]
    layers: list[BasicLayer]
    tests: dict[str, list[TestRecord]]
    dirty: bool
    dirty_suffixes: set[str]
    is_new: bool
    old_prefix: str | None

    @classmethod
    def capture(cls, borehole: Borehole) -> BoreholeSnapshot:
        """捕获钻孔当前状态的快照。

        Args:
            borehole: 钻孔对象

        Returns:
            当前状态的快照对象

        Example:
            >>> snapshot = BoreholeSnapshot.capture(borehole)
        """
        return cls(
            prefix=borehole.prefix,
            hole_type=borehole.hole_type,
            main_lines=list(borehole.main.normalized_lines()),
            layers=copy_layers(borehole.layers),
            tests=copy_tests(borehole.tests),
            dirty=borehole.dirty,
            dirty_suffixes=set(borehole.dirty_suffixes),
            is_new=borehole.is_new,
            old_prefix=borehole.old_prefix,
        )

    def same_content(self, other: BoreholeSnapshot) -> bool:
        """比较两个快照的内容是否相同。

        只比较数据内容，不比较状态标志（dirty、is_new等）。

        Args:
            other: 另一个快照对象

        Returns:
            内容是否相同

        Example:
            >>> snapshot1 = BoreholeSnapshot.capture(borehole)
            >>> # 执行修改...
            >>> snapshot2 = BoreholeSnapshot.capture(borehole)
            >>> snapshot1.same_content(snapshot2)
            False
        """
        return (
            self.prefix == other.prefix
            and self.hole_type == other.hole_type
            and self.main_lines == other.main_lines
            and self.layers == other.layers
            and self.tests == other.tests
        )

    def restore(self, borehole: Borehole) -> None:
        """将快照状态恢复到钻孔对象。

        Args:
            borehole: 要恢复的钻孔对象

        Example:
            >>> snapshot = BoreholeSnapshot.capture(borehole)
            >>> # 执行修改...
            >>> snapshot.restore(borehole)
        """
        borehole.prefix = self.prefix
        borehole.hole_type = self.hole_type
        borehole.main.lines = list(self.main_lines)
        borehole.layers = copy_layers(self.layers)
        borehole.tests = copy_tests(self.tests)
        borehole.dirty = self.dirty
        borehole.dirty_suffixes = set(self.dirty_suffixes)
        borehole.is_new = self.is_new
        borehole.old_prefix = self.old_prefix


@dataclass
class UndoAction:
    """撤销操作类。

    存储一个完整的撤销操作信息。

    Attributes:
        borehole: 操作的钻孔对象
        label: 操作描述标签
        before: 操作前的快照
        after: 操作后的快照

    Example:
        >>> action = UndoAction(borehole, "修改深度", before_snapshot, after_snapshot)
        >>> print(action.label)
        '修改深度'
    """

    borehole: Borehole
    label: str
    before: BoreholeSnapshot
    after: BoreholeSnapshot


class UndoManager:
    """撤销管理器类。

    管理撤销/重做操作栈，支持最多100步历史记录。

    Attributes:
        max_depth: 最大历史记录数
        undo_stack: 撤销操作栈
        redo_stack: 重做操作栈

    Example:
        >>> manager = UndoManager()
        >>> snapshot = BoreholeSnapshot.capture(borehole)
        >>> # 执行修改...
        >>> new_snapshot = BoreholeSnapshot.capture(borehole)
        >>> action = UndoAction(borehole, "修改深度", snapshot, new_snapshot)
        >>> manager.push(action)
        >>> if manager.can_undo():
        ...     action = manager.pop_undo()
        ...     action.before.restore(action.borehole)
    """

    def __init__(self, max_depth: int = 100) -> None:
        """初始化撤销管理器。

        Args:
            max_depth: 最大历史记录数，默认100
        """
        self.max_depth = max_depth
        self.undo_stack: list[UndoAction] = []
        self.redo_stack: list[UndoAction] = []

    def clear(self) -> None:
        """清空所有历史记录。

        Example:
            >>> manager.clear()
        """
        self.undo_stack.clear()
        self.redo_stack.clear()

    def can_undo(self) -> bool:
        """判断是否可以撤销。

        Returns:
            是否有可撤销的操作

        Example:
            >>> if manager.can_undo():
            ...     action = manager.pop_undo()
        """
        return bool(self.undo_stack)

    def can_redo(self) -> bool:
        """判断是否可以重做。

        Returns:
            是否有可重做的操作

        Example:
            >>> if manager.can_redo():
            ...     action = manager.pop_redo()
        """
        return bool(self.redo_stack)

    def push(self, action: UndoAction) -> None:
        """添加撤销操作。

        会清空重做栈，并在超过最大深度时移除最旧的操作。

        Args:
            action: 撤销操作对象

        Example:
            >>> action = UndoAction(borehole, "修改深度", before, after)
            >>> manager.push(action)
        """
        self.undo_stack.append(action)
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def pop_undo(self) -> UndoAction | None:
        """弹出撤销操作。

        Returns:
            撤销操作对象，栈为空时返回None

        Example:
            >>> action = manager.pop_undo()
            >>> if action:
            ...     action.before.restore(action.borehole)
        """
        if not self.undo_stack:
            return None
        return self.undo_stack.pop()

    def pop_redo(self) -> UndoAction | None:
        """弹出重做操作。

        Returns:
            重做操作对象，栈为空时返回None

        Example:
            >>> action = manager.pop_redo()
            >>> if action:
            ...     action.after.restore(action.borehole)
        """
        if not self.redo_stack:
            return None
        return self.redo_stack.pop()

    def push_redo(self, action: UndoAction) -> None:
        """添加重做操作。

        Args:
            action: 重做操作对象

        Example:
            >>> action = UndoAction(borehole, "修改深度", before, after)
            >>> manager.push_redo(action)
        """
        self.redo_stack.append(action)

    def push_undo_without_clearing_redo(self, action: UndoAction) -> None:
        """添加撤销操作，但不清空重做栈。

        用于恢复操作时保留重做历史。

        Args:
            action: 撤销操作对象

        Example:
            >>> action = UndoAction(borehole, "恢复深度", before, after)
            >>> manager.push_undo_without_clearing_redo(action)
        """
        self.undo_stack.append(action)
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)
