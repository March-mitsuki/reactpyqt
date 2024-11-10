from __future__ import annotations
from PyQt6.QtWidgets import QLayout, QHBoxLayout, QVBoxLayout
from loguru import logger

from .validation import is_component_node

# fmt: off
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core import ReactiveNode
    from qt_widget import QT_Widget
# fmt: on


def find_widget_index(layout: QLayout, object_name: str) -> int:
    """
    Find qt widget index in layout by object name.

    If not found, return -1
    """
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        if widget and widget.objectName() == object_name:
            return index
    return -1  # 未找到该objectName的控件


def remove_widgets_from_layout(layout: QLayout, indexes: list[int]):
    # 从后往前删除，避免删除后索引错乱
    for idx in sorted(indexes, reverse=True):
        item = layout.itemAt(idx)
        if item:
            logger.info(
                f"Removing widget {item.widget().objectName()} from layout {layout.objectName()}"
            )
            layout.removeItem(item)
            item.widget().deleteLater()
    layout.update()


def remove_widgets_by_length(
    host_node: ReactiveNode,
    node: ReactiveNode,
    length: int,
):
    if host_node.qt_widget is None:
        raise ValueError("Node has no QT_Widget")
    layout = host_node.qt_widget.layout()

    root_attached_node = node.find_parent(
        lambda node: not is_component_node(node.parent), include_self=True
    )
    if not root_attached_node:
        raise ValueError("Cannot find root attached node")
    prev_widget = root_attached_node.find_virtual_widget_prev_sibling()
    if prev_widget:
        index = find_widget_index(layout, prev_widget.qt_widget.objectName())
        if index < 0:
            raise ValueError(
                f"Cannot find widget {prev_widget.qt_widget.objectName()} in layout"
            )
        index += 1
    else:
        index = 0

    indexes = list(range(index, index + length))
    remove_widgets_from_layout(layout, indexes)


def insert_widgets_to_layout(
    host_node: ReactiveNode,
    node: ReactiveNode,
    widgets: list[QT_Widget],
):
    if host_node.qt_widget is None:
        raise ValueError("Host node has no QT_Widget")
    host_layout = host_node.qt_widget.layout()
    if not isinstance(host_layout, QHBoxLayout) and not isinstance(
        host_layout, QVBoxLayout
    ):
        raise ValueError(
            "insert_widgets_to_layout only supports QHBoxLayout and QVBoxLayout"
        )

    root_attached_node = node.find_parent(
        lambda node: not is_component_node(node.parent), include_self=True
    )
    if not root_attached_node:
        raise ValueError("Cannot find root attached node")
    logger.info(f"insert_widgets_to_layout root_attached_node {root_attached_node}")
    prev_widget = root_attached_node.find_virtual_widget_prev_sibling()
    if prev_widget:
        logger.info(f"insert_widgets_to_layout prev_widget {prev_widget}")
        index = find_widget_index(host_layout, prev_widget.qt_widget.objectName())
        if index < 0:
            raise ValueError(
                f"Cannot find widget {prev_widget.qt_widget.objectName()} in layout {host_layout.objectName()}"
            )
        index += 1
    else:
        logger.info("insert_widgets_to_layout no prev_widget")
        index = 0

    for idx, widget in enumerate(widgets):
        logger.info(
            f"Inserting widget {widget.objectName()} to layout {host_layout.objectName()} at index {index + idx}"
        )
        host_layout.insertWidget(index + idx, widget)
