from __future__ import annotations
from abc import ABC
from typing import Callable, Any
from uuid import uuid4
from loguru import logger

from PyQt6.QtWidgets import (
    QVBoxLayout,
    QMainWindow,
    QApplication,
    QWidget,
)
from PyQt6.QtCore import QThreadPool
import sys

from .qt_widget import QT_Widget, QT_HBox, QT_VBox, QT_Button, QT_Label, QT_Input
from .globalvar import __app__, __is_first_render__, __intervals__
from .reactive import create_effect, SignalAccessor, create_memo, map_list
from .utils.rect import zoom_rect
from .utils.debug import print_layout_contents, print_tree
from .utils.validation import (
    is_main_thread,
    is_virtual_widget_node,
    is_control_flow_node,
)
from .utils.layout import insert_widgets_to_layout, remove_widgets_by_length
from .utils.common import flatten


class VirtualWidget(ABC):
    def __init__(self, *children, **props):
        logger.debug(f"Creating VirtualWidget props {props}")
        self.tag: str | None = props.pop("tag", None)
        self.key: str = props.get("key", str(uuid4()))
        self.children: list[VirtualWidget | Component | ControlFlow] = children
        self.props: dict = props

    def __repr__(self) -> str:
        return f"<VirtualWidget tag={self.tag} key={self.key} props={self.props} children={self.children}>"


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


def create_qt_widget_nested(vwgt: VirtualWidget) -> QT_Widget:
    """
    Will transform VirtualWidget to ReactiveNode tree
    and create QT_Widget for each node.
    """
    node = create_reactive_node(vwgt, None)
    node.make_tree_after_this_node()

    def cb(node: ReactiveNode, _: int):
        if node.parent is None:
            return

        host_node = node.parent.find_virtual_widget_parent(include_self=True)
        add_node = node.find_virtual_widget_child(include_self=True)

        if host_node is None:
            return
        logger.debug(f"Adding {add_node.qt_widget} to {host_node.key}")
        if add_node is None:
            return
        host_node.qt_widget.layout().addWidget(add_node.qt_widget)

    node.for_each_child(cb)

    root_widget = node.find_virtual_widget_child().qt_widget
    if root_widget is None:
        raise ValueError("Root widget is None")
    return root_widget


def create_qt_widget_nested_component(component: Component):
    """
    Will transform Component to ReactiveNode tree
    and create QT_Widget for each node.
    """
    node = create_reactive_node(component, None)
    node.make_tree_after_this_node()

    def cb(node: ReactiveNode, _: int):
        if node.parent is None:
            return

        host_node = node.parent.find_virtual_widget_parent(include_self=True)
        add_node = node.find_virtual_widget_child(include_self=True)

        if host_node is None:
            return
        logger.debug(f"Adding {add_node.qt_widget} to {host_node.key}")
        if add_node is None:
            return
        host_node.qt_widget.layout().addWidget(add_node.qt_widget)

    node.for_each_child(cb)

    root_widget = node.find_virtual_widget_child().qt_widget
    if root_widget is None:
        raise ValueError("Root widget is None")
    logger.debug(f"Create QT_Widget for {component.key}: {root_widget.objectName()}")
    print_layout_contents(root_widget.layout())
    return root_widget


def handle_control_flow_for(parent: ReactiveNode, node: ReactiveNode):
    length = None

    def handler():
        if not is_main_thread():
            raise ValueError("Signal handler must run in main thread")
        global __is_first_render__
        nonlocal length

        host_node = parent.find_virtual_widget_parent(include_self=True)

        items: list[VirtualWidget | Component] = node.control_flow.accessor()
        if not isinstance(items, list):
            raise ValueError(f"Invalid control flow For items {items}")

        current_length = len(items)
        if __is_first_render__:
            length = current_length

        qt_widgets = []
        for item in items:
            if isinstance(item, VirtualWidget):
                qt_widgets.append(create_qt_widget_nested(item))
            elif isinstance(item, Component):
                qt_widgets.append(create_qt_widget_nested_component(item))
            else:
                raise ValueError(f"Invalid item {item}")

        if __is_first_render__:
            if current_length == 0:
                insert_widgets_to_layout(
                    host_node,
                    node,
                    [create_qt_widget(node.control_flow.fallback)],
                )
            else:
                insert_widgets_to_layout(host_node, node, qt_widgets)
        else:
            if isinstance(length, int) and length > 0:
                remove_widgets_by_length(host_node, node, length)

            if current_length == 0:
                insert_widgets_to_layout(
                    host_node,
                    node,
                    [create_qt_widget(node.control_flow.fallback)],
                )
            else:
                insert_widgets_to_layout(host_node, node, qt_widgets)

        if node.control_flow.fallback is not None and current_length == 0:
            length = 1
        else:
            length = current_length

        logger.debug(f"For control flow {node.key} handler done")

    create_effect(handler)


def handle_control_flow_switch(parent: ReactiveNode, node: ReactiveNode):
    logger.debug(f"Handling Switch {node.key}")

    def handler():
        if not is_main_thread():
            raise ValueError("Signal handler must run in main thread")
        global __is_first_render__
        host_node = parent.find_virtual_widget_parent(include_self=True)

        current_condition = node.control_flow.condition()
        current_case: Case | None = None
        for case in node.control_flow.cases:
            if case.when(current_condition):
                current_case = case
                break

        logger.debug(f"Switch {node.key} current case {current_case}")
        if current_case is None:
            if __is_first_render__:
                pass
            else:
                remove_widgets_by_length(host_node, node, 1)
                if node.control_flow.fallback is None:
                    return
        else:
            if isinstance(current_case.render, VirtualWidget):
                qt_widget = create_qt_widget_nested(current_case.render)
            elif isinstance(current_case.render, Component):
                logger.debug(
                    f"Creating QT_Widget for Switch-Case ControlFlow {current_case.render}"
                )
                qt_widget = create_qt_widget_nested_component(current_case.render)
            elif isinstance(current_case.render, ControlFlow):
                raise ValueError("ControlFlow cannot be nested")
            else:
                raise ValueError(f"Invalid render {current_case.render}")

            if __is_first_render__:
                logger.debug(f"First render, adding {qt_widget} to {host_node.key}")
                insert_widgets_to_layout(host_node, node, [qt_widget])
            else:
                remove_widgets_by_length(host_node, node, 1)
                insert_widgets_to_layout(host_node, node, [qt_widget])

    create_effect(handler)


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
        return f"""<ReactiveNode key={
            self.key
        } parent={
            self.parent.key if self.parent else "none"
        } child={
            self.child.key if self.child else "none"
        } sibling={
            self.sibling.key if self.sibling else "none"
        } prev_sibling={
            self.prev_sibling.key if self.prev_sibling else "none"
        }>"""
        # return f"<ReactiveNode tag={self.tag} key={self.key} component={self.component} control_flow={self.control_flow} props={self.props} qt_widget={self.qt_widget}>"
        # return f"<ReactiveNode tag={self.tag} key={self.key} component={self.component} control_flow={self.control_flow} qt_widget={self.qt_widget}>"
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
        logger.debug(
            f"Reconciling {self.key} children", [child.key for child in children]
        )
        prev_sibling = None
        for idx, child in enumerate(children):
            logger.debug(f"Reconciling {self.key} child {child.key}")
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
            logger.debug(f"Reconciling {current_node.key}")
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
        result = ReactiveNode()
        result.parent = parent
        result.control_flow = control_flow
        result.key = control_flow.key

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
    def __init__(self, *, type, key=str(uuid4())):
        self.type = type
        self.key = key

    def __repr__(self) -> str:
        return f"<ControlFlow[{self.__class__.__name__}] key={self.key}>"


def render(container: QT_Widget, component: Component):
    logger.debug("render called")

    def commit_root():
        root_node = ReactiveNode.from_component(component)
        root_node.make_tree_after_this_node()
        print_tree(root_node)

        def cb(node: ReactiveNode, _: int):
            if node.parent is None:
                return

            host_node = node.parent.find_virtual_widget_parent(include_self=True)
            if not host_node:
                return

            if is_control_flow_node(node):
                # if node.control_flow.type == "for":
                if isinstance(node.control_flow, For):
                    handle_control_flow_for(host_node, node)
                # elif node.control_flow.type == "switch":
                elif isinstance(node.control_flow, Switch):
                    handle_control_flow_switch(host_node, node)
                else:
                    raise ValueError(f"Invalid control flow {node.control_flow}")
            else:
                added_node = node.find_virtual_widget_child(include_self=True)
                if not added_node:
                    return

                logger.debug(f"Adding {added_node.key} to {host_node.key}")
                host_node.qt_widget.layout().addWidget(added_node.qt_widget)

        root_node.for_each_child(cb)

        first_hold = root_node.find_virtual_widget_child()
        container.layout().addWidget(first_hold.qt_widget)

        print_layout_contents(container.layout())

    commit_root()
    global __is_first_render__
    __is_first_render__ = False


class MainWindow:
    def __init__(
        self,
        app: Component,
        *,
        title="ReactPyQt",
        geometry=None,
    ):
        global __app__
        if __app__ is None:
            __app__ = QApplication(sys.argv)

        self.qt_main_window = QMainWindow()

        self.qt_main_window.setWindowTitle(title)
        if geometry:
            self.qt_main_window.setGeometry(geometry)
        else:
            scrreen_geom = QApplication.primaryScreen().geometry()
            self.qt_main_window.setGeometry(zoom_rect(scrreen_geom, 0.5))

        self.root = QWidget()
        self.root.setLayout(QVBoxLayout())
        self.qt_main_window.setCentralWidget(self.root)

        render(self.root, app)

    def handle_quit(self):
        global __intervals__
        for interval in __intervals__:
            interval.stop()
        QThreadPool.globalInstance().clear()

    def start(self):
        global __app__
        __app__.aboutToQuit.connect(self.handle_quit)
        self.qt_main_window.show()
        sys.exit(__app__.exec())


########################################
#           Basic Components           #
########################################
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


class For(ControlFlow):
    def __init__(
        self,
        *,
        key=None,
        each: list,
        map_fn: Callable | None = None,
        fallback: Component | VirtualWidget | None = None,
    ):
        super().__init__(type="for", key=key)
        self.map_fn = map_fn
        self.each = each
        self.fallback = fallback
        self.accessor = create_memo(map_list(self.each, self.map_fn))


class Switch(ControlFlow):
    def __init__(
        self,
        *,
        key=None,
        condition: SignalAccessor,
        cases: list[Case],
        fallback: Component | VirtualWidget | None = None,
    ):
        super().__init__(type="switch", key=key)
        self.cases = cases
        self.condition = condition
        self.fallback = fallback


class Case(ControlFlow):
    def __init__(
        self,
        *,
        key=None,
        when: Callable[[Any], bool],
        render: VirtualWidget | Component | ControlFlow,
    ):
        super().__init__(type="case", key=key)
        self.render: VirtualWidget | Component | ControlFlow = render
        self.when = when
