from __future__ import annotations
from abc import ABC
from typing import Callable, Any
from uuid import uuid4
from PyQt6.QtWidgets import QLayout, QVBoxLayout, QHBoxLayout
from loguru import logger

from widget import QT_Widget, QT_HBox, QT_VBox, QT_Button, QT_Label, QT_Input

import threading
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QObject


def flatten(nested_list: list) -> list:
    """
    将嵌套列表展开
    """
    stack = list(nested_list[::-1])  # 将列表倒序入栈
    flat_list = []

    while stack:
        item = stack.pop()

        if isinstance(item, list):
            # 如果是列表，将其中元素倒序入栈
            stack.extend(item[::-1])
        else:
            flat_list.append(item)

    return flat_list


def is_component_node(obj: ReactiveNode) -> bool:
    return obj.component is not None and obj.tag is None


def is_virtual_widget_node(obj: ReactiveNode) -> bool:
    return obj.component is None and obj.tag is not None


def remove_widgets_from_layout(layout: QLayout, indexes: list[int]):
    # 从后往前删除，避免删除后索引错乱
    for idx in sorted(indexes, reverse=True):
        print(f"Removing widget from {layout} at index {idx}")
        item = layout.itemAt(idx)
        print("Removing item", item)
        if item:
            layout.removeWidget(item.widget())


def remove_widgets_by_length(node: ReactiveNode, start: int, length: int):
    if node.qt_widget is None:
        raise ValueError("Node has no QT_Widget")
    layout = node.qt_widget.layout()
    indexes = list(range(start, start + length))
    print(f"Removing widgets by indexes {indexes}")
    remove_widgets_from_layout(layout, indexes)


def remove_widgets_by_indexes(node: ReactiveNode, indexes: list[int]):
    if node.qt_widget is None:
        raise ValueError("Node has no QT_Widget")
    layout = node.qt_widget.layout()
    remove_widgets_from_layout(layout, indexes)


def insert_widgets_to_layout(layout: QLayout, start: int, widgets: list[QT_Widget]):
    if not isinstance(layout, QHBoxLayout) and not isinstance(layout, QVBoxLayout):
        raise ValueError(
            "insert_widgets_to_layout only supports QHBoxLayout and QVBoxLayout"
        )

    for idx, widget in enumerate(widgets):
        layout.insertWidget(start + idx, widget)


class Timeout(QRunnable):
    class TimtoutSignal(QObject):
        timeout = pyqtSignal()

    def __init__(self, timeout: int):
        super().__init__()
        self.timeout = timeout
        self.signal = self.TimtoutSignal()

    @pyqtSlot()
    def run(self):
        import time

        time.sleep(self.timeout)
        self.signal.timeout.emit()


def set_timeout(func, sec):
    timeout = Timeout(sec)
    timeout.signal.timeout.connect(func)
    QThreadPool.globalInstance().start(timeout)


__listener__ = None
__is_first_render__ = True
__app__ = None


SignalAccessor = Callable[[], Any]
SignalSetter = Callable[[Any], None]


class Signal:
    def __init__(self, init_value):
        super().__init__()
        self._value = init_value
        self._subscribers = set()

    def __repr__(self) -> str:
        return f"<Signal value={self._value}>"

    def get(self):
        if __listener__:
            self._subscribers.add(__listener__)
        return self._value

    def set(self, next_value):
        if callable(next_value):
            self._value = next_value(self._value)
        else:
            if self._value == next_value:
                return
            self._value = next_value

        for subscriber in self._subscribers:
            subscriber()

    def subscribe(self, cb):
        self._subscribers.add(cb)


def create_effect(cb):
    global __listener__
    prev_listener = __listener__
    __listener__ = cb
    cb()
    __listener__ = prev_listener


def create_signal(value) -> tuple[SignalAccessor, SignalSetter]:
    s = Signal(value)

    return (s.get, s.set)


def create_memo(cb):
    value, set_value = create_signal(None)
    create_effect(lambda: set_value(cb()))
    return value


def untrack(cb):
    global __listener__
    prev_listener = __listener__
    __listener__ = None
    try:
        return cb()
    finally:
        __listener__ = prev_listener


def on_mount(cb):
    create_effect(lambda: untrack(cb))


def map_list(list: SignalAccessor, map_cb: Callable) -> Callable:
    result, set_result = create_signal([])
    create_effect(lambda: set_result([map_cb(item) for item in list()]))
    return result


class VirtualWidget(ABC):
    def __init__(self, *children, **props):
        logger.debug(f"Creating VirtualWidget props {props}")
        self.tag: str | None = props.pop("tag", None)
        self.key: str = props.pop("key", str(uuid4()))
        self.children: list[VirtualWidget | Component | SignalAccessor] = children
        self.props: dict = props

    def __repr__(self) -> str:
        return f"<VirtualWidget tag={self.tag} key={self.key} props={self.props} children={self.children}>"


class Button(VirtualWidget):
    def __init__(self, text, **props):
        super().__init__(tag="button", **props)
        self.text = text


class Label(VirtualWidget):
    def __init__(self, text, **props):
        super().__init__(tag="label", **props)
        self.text = text


class Input(VirtualWidget):
    def __init__(self, **props):
        super().__init__(tag="input", **props)


class VBox(VirtualWidget):
    def __init__(self, *children, **props):
        super().__init__(tag="vbox", *children, **props)


class HBox(VirtualWidget):
    def __init__(self, *children, **props):
        super().__init__(tag="hbox", *children, **props)


def create_qt_widget(node: VirtualWidget) -> QT_Widget:
    logger.debug(f"Creating QT_Widget for {node}")
    tag = node.tag
    if tag == "button":
        return QT_Button(node.text, **node.props)
    elif tag == "label":
        return QT_Label(node.text, **node.props)
    elif tag == "input":
        return QT_Input(**node.props)
    elif tag == "vbox":
        return QT_VBox(**node.props)
    elif tag == "hbox":
        return QT_HBox(**node.props)
    else:
        raise ValueError(f"Invalid tag: {tag}")


def create_reactive_node(
    component: Component | VirtualWidget,
    parent: ReactiveNode,
):
    if isinstance(component, Component):
        return ReactiveNode.from_component(component, parent)
    elif isinstance(component, VirtualWidget):
        result = ReactiveNode.from_virtual_widget(component, parent)
        result.qt_widget = create_qt_widget(result)
        return result
    else:
        raise ValueError(f"Invalid component {component}")


def is_main_thread():
    return threading.get_ident() == threading.main_thread().ident


def handle_for_control_flow(parent: ReactiveNode, child: For, idx: int):
    def handler():
        if not is_main_thread():
            raise ValueError("Signal handler must run in main thread")
        global __is_first_render__

        # 要求 signal 返回一个 list
        # list 中的东西是当前节点的 children
        # 但 reconcile_children() 只会在初始化时调用一次
        # 而 handler() 会在每次 signal 变化时调用
        # 所以需要一个逻辑来处理 signal 变化时的 children 变化
        items: list[VirtualWidget | Component] = child.accessor()
        if not isinstance(items, list):
            items = [items]

        if parent.side_effect is None:
            parent.side_effect = SignalChidren()

        host_node = parent.side_effect.host_node
        if host_node is None:
            host_node = parent.find_virtual_widget_parent()
            parent.side_effect.host_node = host_node
        parent.side_effect.old_start_idx = idx
        if parent.side_effect.host_node is None:
            raise ValueError("Parent not found")

        current_length = len(items)
        if __is_first_render__:
            length = len(items)
        else:
            length = parent.side_effect.old_length

        # 暂且要求内容必须都是可以直接创建 qt_widget 的 VirtualWidget
        qt_widgets = []
        for item in items:
            qt_widgets.append(create_qt_widget(item))

        if __is_first_render__:
            if current_length == 0:
                host_node.qt_widget.layout().addWidget(create_qt_widget(child.fallback))
            else:
                for widget in qt_widgets:
                    host_node.qt_widget.layout().addWidget(widget)
        else:
            if isinstance(length, int) and length > 0:
                # 如果有需要删除的 widget
                remove_widgets_by_length(
                    host_node, parent.side_effect.old_start_idx, length
                )
            if current_length == 0:
                host_node.qt_widget.layout().addWidget(create_qt_widget(child.fallback))
            else:
                insert_widgets_to_layout(
                    host_node.qt_widget.layout(),
                    parent.side_effect.old_start_idx,
                    qt_widgets,
                )
        if child.fallback is not None and current_length == 0:
            parent.side_effect.old_length = 1
        else:
            parent.side_effect.old_length = current_length

    create_effect(handler)


class SignalChidren:
    def __init__(self):
        self.old_start_idx: int | None = None
        self.old_length: int | None = None
        self.host_node: ReactiveNode | None = None


class ReactiveNode(VirtualWidget):
    def __init__(self, *children, **props):
        logger.debug(f"Creating ReactiveNode props {props}")
        super().__init__(*children, **props)
        self.component: Component | None = None
        self.alternate: ReactiveNode | None = None
        self.qt_widget: QT_Widget | None = None
        self.child: ReactiveNode | None = None
        self.parent: ReactiveNode | None = None
        self.sibling: ReactiveNode | None = None
        self.side_effect: SignalChidren | None = None

    def __repr__(self) -> str:
        return f"<ReactiveNode tag={self.tag} key={self.key} component={self.component} props={self.props} qt_widget={self.qt_widget}>"
        # return f"<ReactiveNode tag={self.tag} key={self.key} component={self.component} props={self.props}>"
        # return f"<ReactiveNode tag={self.tag} key={self.key} component={self.component}>"

    def find_parent(self, cb: Callable[[ReactiveNode], bool]):
        node = self
        while node is not None:
            if cb(node):
                return node
            node = node.parent
        return None

    def find_child(self, cb: Callable[[ReactiveNode], bool]):
        node = self
        while node is not None:
            if cb(node):
                return node
            node = node.child
        return None

    def find_virtual_widget_parent(self):
        return self.find_parent(lambda node: is_virtual_widget_node(node))

    def find_virtual_widget_child(self):
        return self.find_child(lambda node: is_virtual_widget_node(node))

    def reconcile_children(self):
        nested = []

        children: list[VirtualWidget | Component | ControlFlow] = flatten(self.children)
        prev_sibling = None
        for idx, child in enumerate(children):
            if isinstance(child, ControlFlow):
                if isinstance(child, For):
                    # 现在的流程是全部生成完之后才会使用 commit_root() 添加到 layout
                    # 但这里的 handler() 会立即执行, 所以会破坏这个流程, 要想想办法
                    handle_for_control_flow(self, child, idx)
                else:
                    raise ValueError(f"Invalid ControlFlow {child}")
            else:
                child_node = create_reactive_node(child, self)

                if idx == 0:
                    self.child = child_node
                else:
                    prev_sibling.sibling = child_node
                prev_sibling = child_node
                nested.append(child_node)

        return nested

    def make_tree_after_this_node(self):
        stack = [self]

        while len(stack) > 0:
            current_node = stack.pop()
            nested_child = current_node.reconcile_children()
            stack.extend(nested_child)

    def to_tree(self):
        stack = [self]

        while len(stack) > 0:
            current_node = stack.pop()
            children = flatten(current_node.children)  # 展开 list.map() 的结果

            prev_sibling = None
            for idx, child in enumerate(children):
                child_node = create_reactive_node(child, current_node)

                if idx == 0:
                    current_node.child = child_node
                else:
                    prev_sibling.sibling = child_node
                prev_sibling = child_node
                stack.append(child_node)

    def for_each_child(
        self,
        cb: Callable[[ReactiveNode, int], None] | None = None,
        exit_cb: Callable[[ReactiveNode, int], None] | None = None,
    ):
        stack: list[tuple[ReactiveNode, int, bool]] = [(self, 0, False)]
        while len(stack) > 0:
            current, depth, visited = stack.pop()
            if not visited:
                cb(current, depth) if cb else None
                stack.append((current, depth, True))
                if current.sibling:
                    stack.append((current.sibling, depth, False))
                if current.child:
                    stack.append((current.child, depth + 1, False))
            else:
                exit_cb(current, depth) if exit_cb else None

    def print_tree(self):
        self.for_each_child(lambda node, depth: print(depth, "  " * depth, node))

    @staticmethod
    def from_component(component: Component, parent: ReactiveNode | None = None):
        logger.debug(f"Creating ReactiveNode from {component}")
        result = ReactiveNode(component.render(), **component.props)
        result.component = component
        result.parent = parent

        return result

    @staticmethod
    def from_virtual_widget(virtual_widget: VirtualWidget, parent: ReactiveNode):
        logger.debug(f"Creating ReactiveNode from {virtual_widget}")
        result = ReactiveNode(
            *virtual_widget.children,
            tag=virtual_widget.tag,
            key=virtual_widget.key,
            **virtual_widget.props,
        )
        result.parent = parent

        if result.tag == "button" or result.tag == "label":
            result.text = virtual_widget.text

        result.qt_widget = create_qt_widget(result)

        return result


class Component(ABC):
    def __init__(self, **props):
        self.props = props

    def __repr__(self) -> str:
        return f"<Component[{self.__class__.__name__}] props={self.props}>"

    def render(self) -> VirtualWidget | Component | ControlFlow:
        """
        Fine-Grained Reactivity 架构下的 render 只在初始化时运行一次
        """
        raise NotImplementedError("render method is not implemented")


class ControlFlow(ABC):
    """
    ControFlow must have a accessor property
    """

    def __repr__(self) -> str:
        return f"<ControlFlow[{self.__class__.__name__}] accessor={self.accessor}>"


class For(ControlFlow):
    def __init__(
        self,
        *,
        each: list,
        map_fn: Callable | None = None,
        fallback: Component | VirtualWidget | None = None,
    ):
        super().__init__()
        self.map_fn = map_fn
        self.each = each
        self.fallback = fallback
        self.accessor = create_memo(map_list(self.each, self.map_fn))


def render(container: QT_Widget, component: Component):
    logger.debug("Rendering component: {component}")
    # pool = QThreadPool.globalInstance()
    # work_loop = WorkLoop()
    # pool.start(work_loop)

    def commit_root():
        root_node = ReactiveNode.from_component(component)
        # root_node.to_tree()
        root_node.make_tree_after_this_node()
        root_node.print_tree()

        def cb(node: ReactiveNode, _: int):
            if node.parent is not None and node.parent.qt_widget is not None:
                if node.qt_widget is None and node.component is not None:
                    logger.debug(f"Adding {node.child} to {node.parent}")
                    node.parent.qt_widget.layout().addWidget(node.child.qt_widget)
                    return

                if node.qt_widget is not None:
                    logger.debug(f"Adding {node} to {node.parent}")
                    node.parent.qt_widget.layout().addWidget(node.qt_widget)
                    return

                raise ValueError(f"Invalid node {node}")

        root_node.for_each_child(cb)
        container.layout().addWidget(root_node.child.qt_widget)

    commit_root()
    global __is_first_render__
    __is_first_render__ = False


if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout
    from PyQt6.QtCore import QRect

    logger.remove()
    logger.add(sys.stdout, level="INFO")

    class Nav(Component):
        def render(self):
            is_logged_in = self.props.get("is_logged_in")
            return HBox(
                [
                    Label("Home", key="nav-home"),
                    Label("Dashboard", key="nav-dashboard"),
                    Label("Logout", key="nav-logout"),
                ]
                if is_logged_in()
                else [
                    Label("Home", key="nav-home"),
                    Label("Login", key="nav-login"),
                    Label("Register", key="nav-register"),
                ],
                spacing=10,
                key="nav",
            )

    class App(Component):
        def __init__(self):
            self.props = {
                "key": "app-component",
            }

        def render(self):
            is_logged_in, set_is_logged_in = create_signal(False)
            set_timeout(lambda: set_is_logged_in(True), 2)
            create_effect(lambda: print("is_logged_in", is_logged_in()))
            on_mount(lambda: print("App mounted"))

            todo, set_todo = create_signal(["Buy milk", "Buy eggs"])
            set_timeout(lambda: set_todo(["Buy milk", "Buy eggs", "Buy bread"]), 3)
            set_timeout(lambda: set_todo(lambda prev: [*prev, "Do homework"]), 5)
            set_timeout(lambda: set_todo([]), 7)
            set_timeout(lambda: set_todo(["Play WuWa"]), 9)
            create_effect(lambda: print("todo", todo()))

            def render_list(item):
                print("Rendering item", item)
                return Label(item, key=item)

            return VBox(
                Nav(is_logged_in=is_logged_in, key="nav-component"),
                Label("Welcome to ReactivePyQt", key="welcome"),
                Input(key="input"),
                VBox(
                    Label("Todo List", key="todo_label"),
                    For(
                        each=todo,
                        map_fn=render_list,
                        fallback=Label("No todo items", key="no-todo"),
                    ),
                    spacing=5,
                    key="todo_list",
                ),
                key="app",
            )

    def zoom_rect(rect: QRect, factor):
        """中心缩放 QRect"""
        width = int(rect.width() * factor)
        height = int(rect.height() * factor)
        x = int(rect.x() - (width - rect.width()) / 2)
        y = int(rect.y() - (height - rect.height()) / 2)
        return QRect(x, y, width, height)

    class ReactPyQt(QMainWindow):
        def __init__(self):
            super().__init__()

            self.setWindowTitle("ReactPyQt")
            scrreen_geom = QApplication.primaryScreen().geometry()
            self.setGeometry(zoom_rect(scrreen_geom, 0.5))

            self.root = QWidget()
            self.root.setLayout(QVBoxLayout())
            self.setCentralWidget(self.root)

            render(self.root, App())

    __app__ = QApplication(sys.argv)
    window = ReactPyQt()
    window.show()
    sys.exit(__app__.exec())
