from __future__ import annotations
from abc import ABC
from typing import Callable, Any
from uuid import uuid4
from PyQt6.QtWidgets import QLayout, QVBoxLayout, QHBoxLayout
from loguru import logger

from widget import QT_Widget, QT_HBox, QT_VBox, QT_Button, QT_Label, QT_Input

import threading
from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QObject, QTimer


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
    return obj.component is not None and obj.tag is None and obj.control_flow is None


def is_virtual_widget_node(obj: ReactiveNode) -> bool:
    return obj.component is None and obj.tag is not None and obj.control_flow is None


def is_control_flow_node(obj: ReactiveNode) -> bool:
    return obj.component is None and obj.tag is None and obj.control_flow is not None


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
            logger.info(f"Removing widget {item.widget().objectName()}")
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

    prev_widget = node.find_virtual_widget_prev_sibling()
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
    logger.info(f"Removing widgets from {layout.objectName()} by indexes {indexes}")
    remove_widgets_from_layout(layout, indexes)


def remove_widgets_by_indexes(node: ReactiveNode, indexes: list[int]):
    if node.qt_widget is None:
        raise ValueError("Node has no QT_Widget")
    layout = node.qt_widget.layout()
    remove_widgets_from_layout(layout, indexes)


def insert_widgets_to_layout(
    host_layout: QLayout,
    node: ReactiveNode,
    widgets: list[QT_Widget],
):
    if not isinstance(host_layout, QHBoxLayout) and not isinstance(
        host_layout, QVBoxLayout
    ):
        raise ValueError(
            "insert_widgets_to_layout only supports QHBoxLayout and QVBoxLayout"
        )

    prev_widget = node.find_virtual_widget_prev_sibling()
    if prev_widget:
        index = find_widget_index(host_layout, prev_widget.qt_widget.objectName())
        if index < 0:
            raise ValueError(
                f"Cannot find widget {prev_widget.qt_widget.objectName()} in layout"
            )
        index += 1
    else:
        index = 0

    for idx, widget in enumerate(widgets):
        logger.info(f"Inserting widget {widget.objectName()} at index {index + idx}")
        host_layout.insertWidget(index + idx, widget)


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


class Interval:
    def __init__(self, callback, interval):
        self.callback = callback
        self.interval = interval
        self.timer = QTimer()
        self.timer.timeout.connect(self.callback)

    def start(self):
        self.timer.start(self.interval)

    def stop(self):
        self.timer.stop()


def set_timeout(func, sec):
    timeout = Timeout(sec)
    timeout.signal.timeout.connect(func)
    QThreadPool.globalInstance().start(timeout)


def set_interval(func, sec):
    interval = Interval(func, sec)
    interval.start()
    return interval


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
        self.key: str = props.get("key", str(uuid4()))
        self.children: list[VirtualWidget | Component | ControlFlow] = children
        self.props: dict = props

    def __repr__(self) -> str:
        return f"<VirtualWidget tag={self.tag} key={self.key} props={self.props} children={self.children}>"


class Button(VirtualWidget):
    def __init__(self, text, **props):
        super().__init__(tag="button", text=text, **props)


class Label(VirtualWidget):
    def __init__(self, text, **props):
        super().__init__(tag="label", text=text, **props)


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
        return QT_Button(**node.props)
    elif tag == "label":
        return QT_Label(**node.props)
    elif tag == "input":
        return QT_Input(**node.props)
    elif tag == "vbox":
        return QT_VBox(**node.props)
    elif tag == "hbox":
        return QT_HBox(**node.props)
    else:
        raise ValueError(f"Invalid tag: {tag}")


def create_reactive_node(
    child: Component | VirtualWidget | ControlFlow,
    parent: ReactiveNode,
):
    if isinstance(child, Component):
        return ReactiveNode.from_component(child, parent)
    elif isinstance(child, VirtualWidget):
        result = ReactiveNode.from_virtual_widget(child, parent)
        result.qt_widget = create_qt_widget(result)
        return result
    elif isinstance(child, ControlFlow):
        return ReactiveNode.from_control_flow(child, parent)
    else:
        raise ValueError(f"Invalid component {child}")


def create_qt_widget_for_single_component(component: Component):
    node = create_reactive_node(component, None)
    node.make_tree_after_this_node()

    def cb(node: ReactiveNode, _: int):
        if is_virtual_widget_node(node):
            node.qt_widget = create_qt_widget(node)

        if node.parent is None:
            return

        host_node = node.parent.find_virtual_widget_parent(include_self=True)
        add_node = node.find_virtual_widget_child(include_self=True)

        if host_node is None:
            return
        logger.info(f"Adding {add_node.qt_widget} to {host_node.key}")
        if add_node is None:
            return
        host_node.qt_widget.layout().addWidget(add_node.qt_widget)

    node.for_each_child(cb)

    root_widget = node.find_virtual_widget_child().qt_widget
    if root_widget is None:
        raise ValueError("Root widget is None")
    return root_widget


def is_main_thread():
    return threading.get_ident() == threading.main_thread().ident


def handle_for_control_flow(
    parent: ReactiveNode,
    child: ReactiveNode,
):
    if not isinstance(child.control_flow, For):
        raise ValueError("ControlFlow must be For")

    host_node = parent.find_virtual_widget_parent(include_self=True)
    length = None

    def handler():
        if not is_main_thread():
            raise ValueError("Signal handler must run in main thread")
        global __is_first_render__
        nonlocal host_node, length

        items: list[VirtualWidget | Component] = child.control_flow.accessor()
        if not isinstance(items, list):
            raise ValueError(f"Invalid control flow For items {items}")

        current_length = len(items)
        if __is_first_render__:
            length = current_length

        qt_widgets = []
        for item in items:
            if isinstance(item, VirtualWidget):
                qt_widgets.append(create_qt_widget(item))
            elif isinstance(item, Component):
                qt_widgets.append(create_qt_widget_for_single_component(item))
            else:
                raise ValueError(f"Invalid item {item}")

        if __is_first_render__:
            if current_length == 0:
                insert_widgets_to_layout(
                    host_node.qt_widget.layout(),
                    child,
                    [create_qt_widget(child.control_flow.fallback)],
                )
            else:
                insert_widgets_to_layout(
                    host_node.qt_widget.layout(), child, qt_widgets
                )
        else:
            if isinstance(length, int) and length > 0:
                remove_widgets_by_length(host_node, child, length)

            if current_length == 0:
                insert_widgets_to_layout(
                    host_node.qt_widget.layout(),
                    child,
                    [create_qt_widget(child.control_flow.fallback)],
                )
            else:
                insert_widgets_to_layout(
                    host_node.qt_widget.layout(), child, qt_widgets
                )

        if child.control_flow.fallback is not None and current_length == 0:
            length = 1
        else:
            length = current_length

        print(f"For control flow {child.key} handler done")

    create_effect(handler)


class SideEffectControlFlow:
    def __init__(self, *, type):
        self.type: str = type
        self.source_node: ReactiveNode | None = None
        self.old_start_idx: int | None = None
        self.old_length: int | None = None
        self.host_node: ReactiveNode | None = None


class ReactiveNode(VirtualWidget):
    def __init__(self, *children, **props):
        logger.debug(f"Creating ReactiveNode props {props}")
        super().__init__(*children, **props)
        self.component: Component | None = None
        self.control_flow: ControlFlow | None = None
        self.qt_widget: QT_Widget | None = None
        self.child: ReactiveNode | None = None
        self.parent: ReactiveNode | None = None
        self.sibling: ReactiveNode | None = None
        self.prev_sibling: ReactiveNode | None = None

    def __repr__(self) -> str:
        # return f"""<ReactiveNode tag={
        #     self.tag
        # } parent={
        #     self.parent.key if self.parent else "none"
        # } child={
        #     self.child.key if self.child else "none"
        # } sibling={
        #     self.sibling.key if self.sibling else "none"
        # } prev_sibling={
        #     self.prev_sibling.key if self.prev_sibling else "none"
        # }>"""
        # return f"<ReactiveNode tag={self.tag} key={self.key} component={self.component} control_flow={self.control_flow} props={self.props} qt_widget={self.qt_widget}>"
        return f"<ReactiveNode tag={self.tag} key={self.key} component={self.component} control_flow={self.control_flow} qt_widget={self.qt_widget}>"
        # return f"<ReactiveNode tag={self.tag} key={self.key} component={self.component} control_flow={self.control_flow} props={self.props}>"
        # return f"<ReactiveNode tag={self.tag} key={self.key} component={self.component} control_flow={self.control_flow}>"

    def find_parent(
        self,
        cb: Callable[[ReactiveNode], bool],
        *,
        include_self=True,
    ):
        if include_self:
            node = self
        else:
            node = self.parent

        while node is not None:
            if cb(node):
                return node
            node = node.parent
        return None

    def find_child(
        self,
        cb: Callable[[ReactiveNode], bool],
        *,
        include_self=True,
    ):
        if include_self:
            node = self
        else:
            node = self.child

        while node is not None:
            if cb(node):
                return node
            node = node.child
        return None

    def find_prev_sibling(
        self,
        cb: Callable[[ReactiveNode], bool],
        *,
        include_self=True,
    ):
        if include_self:
            node = self
        else:
            node = self.prev_sibling

        while node is not None:
            if cb(node):
                return node
            node = node.prev_sibling
        return None

    def find_virtual_widget_parent(self, *, include_self=True):
        return self.find_parent(
            lambda node: is_virtual_widget_node(node),
            include_self=include_self,
        )

    def find_virtual_widget_child(self, *, include_self=True):
        return self.find_child(
            lambda node: is_virtual_widget_node(node),
            include_self=include_self,
        )

    def find_virtual_widget_prev_sibling(self, *, include_self=True):
        return self.find_prev_sibling(
            lambda node: is_virtual_widget_node(node),
            include_self=include_self,
        )

    def reconcile_children(self):
        nested = []

        children: list[VirtualWidget | Component | ControlFlow] = flatten(self.children)
        print(f"Reconciling {self.key} children", [child.key for child in children])
        prev_sibling = None
        for idx, child in enumerate(children):
            print(f"Reconciling {self.key} child {child.key}")
            child_node = create_reactive_node(child, self)

            if idx == 0:
                self.child = child_node
            else:
                child_node.prev_sibling = prev_sibling
                prev_sibling.sibling = child_node

            prev_sibling = child_node
            nested.append(child_node)

        return nested

    def make_tree_after_this_node(self):
        stack = [self]

        while len(stack) > 0:
            current_node = stack.pop()
            print(f"Reconciling {current_node.key}")
            nested_child = current_node.reconcile_children()
            stack.extend(nested_child)

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
            **virtual_widget.props,
        )
        result.parent = parent

        result.qt_widget = create_qt_widget(result)

        return result

    @staticmethod
    def from_control_flow(control_flow: ControlFlow, parent: ReactiveNode):
        result = None
        if isinstance(control_flow, For):
            result = ReactiveNode()
            result.parent = parent
            result.control_flow = control_flow
            result.key = control_flow.key
        else:
            raise ValueError(f"Invalid ControlFlow {control_flow}")
        return result


class Component(ABC):
    def __init__(self, **props):
        self.key = props.get("key", str(uuid4()))
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

    def __init__(self, key: str):
        self.key = key
        self.accessor = None

    def __repr__(self) -> str:
        return f"<ControlFlow[{self.__class__.__name__}] key={self.key} accessor={self.accessor}>"


class For(ControlFlow):
    def __init__(
        self,
        *,
        each: list,
        map_fn: Callable | None = None,
        fallback: Component | VirtualWidget | None = None,
        key: str = str(uuid4()),
    ):
        super().__init__(key=key)
        self.map_fn = map_fn
        self.each = each
        self.fallback = fallback
        self.accessor = create_memo(map_list(self.each, self.map_fn))


def print_layout_contents(layout: QLayout, level=0):
    # logger.info(
    #     f"Printing layout {layout.objectName()} ({type(layout).__name__}) items {layout.count()}"
    # )

    indent = "  " * level
    for i in range(layout.count()):
        item = layout.itemAt(i)
        widget = item.widget()
        sub_layout = item.layout()
        widget_layout = widget.layout() if widget else None

        if widget:
            # 如果是QWidget，打印其信息
            print(f"{indent}Widget: {widget.objectName()} ({type(widget).__name__})")

        if widget_layout is not None:
            # 如果这个widget有一个布局，那么递归调用
            # logger.info(f"Have widget layout {widget_layout}")
            print(
                f"{indent}Widget-layout: {widget_layout.objectName()} ({type(widget.layout()).__name__})"
            )
            print_layout_contents(widget.layout(), level + 1)

        if sub_layout:
            # 如果是子布局，递归调用这个函数
            print(
                f"{indent}Layout: {widget_layout.objectName()} {type(sub_layout).__name__}"
            )
            print_layout_contents(sub_layout, level + 1)


def render(container: QT_Widget, component: Component):
    logger.debug("render called")

    def commit_root():
        root_node = ReactiveNode.from_component(component)
        root_node.make_tree_after_this_node()
        root_node.print_tree()

        def cb(node: ReactiveNode, _: int):
            if node.parent is None:
                return

            host_node = node.parent.find_virtual_widget_parent(include_self=True)
            if not host_node:
                return

            if is_control_flow_node(node):
                if isinstance(node.control_flow, For):
                    handle_for_control_flow(host_node, node)
                else:
                    raise ValueError(f"Invalid control flow {node.control_flow}")
            else:
                added_node = node.find_virtual_widget_child(include_self=True)
                if not added_node:
                    return

                logger.info(f"Adding {added_node.key} to {host_node.key}")
                host_node.qt_widget.layout().addWidget(added_node.qt_widget)

        root_node.for_each_child(cb)

        first_hold = root_node.find_virtual_widget_child()
        container.layout().addWidget(first_hold.qt_widget)

        # logger.info(f"root_node.child {root_node.child}")
        # print_layout_contents(container.layout())

        # def find_widget(node: ReactiveNode, _: int):
        #     if node.key == "todo_list":
        #         logger.info(
        #             f"Found todo_list {node}, layout {node.qt_widget.layout().objectName()}"
        #         )
        #         print_layout_contents(node.qt_widget.layout())
        #     if node.key == "nav":
        #         logger.info(
        #             f"Found nav {node}, layout {node.qt_widget.layout().objectName()}"
        #         )
        #         print_layout_contents(node.qt_widget.layout())

        # root_node.for_each_child(find_widget)

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

    class TodoItem(Component):
        def render(self):
            return HBox(
                Label("Item: ", key=f"todo-item-title-{self.props.get('item')}"),
                Label(self.props.get("item"), key=self.props.get("item")),
                key=f"todo-item-hbox-{self.props.get('item')}",
            )

    class App(Component):
        def __init__(self):
            self.props = {
                "key": "app-component",
            }

        def render(self):
            is_logged_in, set_is_logged_in = create_signal(False)
            set_timeout(lambda: set_is_logged_in(True), 2)
            # create_effect(lambda: print("is_logged_in", is_logged_in()))
            # on_mount(lambda: print("App mounted"))

            todo, set_todo = create_signal(["First Render", "Buy something"])
            create_effect(lambda: logger.info("todo changed: {}", todo()))

            # count, set_count = create_signal(0)

            def render_list(item):
                return TodoItem(item=item, key=f"todo-item-component-{item}")

            def add_todo():
                set_todo(lambda prev: [*prev, f"New Todo {len(prev)}"])

            return VBox(
                Nav(is_logged_in=is_logged_in, key="nav-component"),
                Label("Welcome to ReactivePyQt", key="welcome"),
                # Label("Count"),
                Input(key="input"),
                VBox(
                    Label("Todo List", key="todo_label"),
                    For(
                        each=todo,
                        map_fn=render_list,
                        fallback=Label("No todo items", key="no-todo"),
                        key="todo_list_for",
                    ),
                    spacing=5,
                    key="todo_list",
                ),
                Button("Add Todo", key="add-todo", on_click=add_todo),
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

    def handle_quit():
        QThreadPool.globalInstance().clear()

    __app__ = QApplication(sys.argv)
    __app__.aboutToQuit.connect(handle_quit)

    window = ReactPyQt()
    window.show()
    sys.exit(__app__.exec())
