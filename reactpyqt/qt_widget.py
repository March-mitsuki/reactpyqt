from __future__ import annotations
from typing import Callable, Any
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLayout,
    QLabel,
    QPushButton,
    QLineEdit,
    QScrollArea,
)
from PyQt6.QtCore import Qt
from loguru import logger

from .reactive import create_effect, SignalAccessor


def _set_with_operation(set_fn: Callable, value: Any, operation: str):
    if operation == "*":
        set_fn(*value)
    elif operation == "**":
        set_fn(**value)
    elif operation == "str":
        set_fn(str(value))
    elif operation == "none":
        set_fn(value)
    else:
        raise ValueError(f"Invalid operation: {operation}")


def handle_accessor(
    set_fn: Callable,
    value: SignalAccessor | Any,
    *,
    operation="none",
):
    if callable(value):

        def handler():
            nonlocal value

            _value = value()
            _set_with_operation(set_fn, _value, operation)

        create_effect(handler)
    else:
        _set_with_operation(set_fn, value, operation)


def apply_widget_props(widget: QWidget, **props):
    for key, value in props.items():
        if key == "qss":
            # widget.setStyleSheet(value)
            handle_accessor(widget.setStyleSheet, value)
        elif key == "minimum_size":
            # widget.setMinimumSize(*value)
            handle_accessor(widget.setMinimumSize, value, operation="*")
        elif key == "maximum_size":
            # widget.setMaximumSize(*value)
            handle_accessor(widget.setMaximumSize, value, operation="*")
        elif key == "size":
            # widget.setFixedSize(*value)
            handle_accessor(widget.setFixedSize, value, operation="*")


def apply_layout_props(layout: QLayout, **props):
    for key, value in props.items():
        if key == "margin":
            # layout.setContentsMargins(*value)
            handle_accessor(layout.setContentsMargins, value, operation="*")
        elif key == "spacing":
            # layout.setSpacing(value)
            handle_accessor(layout.setSpacing, value)
        elif key == "alignment":
            # layout.setAlignment(value)
            handle_accessor(layout.setAlignment, value)
        elif key == "size_policy":
            # layout.setSizeConstraint(value)
            handle_accessor(layout.setSizeConstraint, value)
        elif key == "alignment":
            # layout.setAlignment(value)
            handle_accessor(layout.setAlignment, value)


def apply_style_props(widget: QWidget, layout: QLayout, **props):
    apply_widget_props(widget, **props)
    apply_layout_props(layout, **props)


def create_widget(widget: QT_Widget | str | int):
    if isinstance(widget, QT_Widget):
        return widget
    elif isinstance(widget, str):
        return QLabel(widget)
    elif isinstance(widget, (int, float)):
        return QLabel(str(widget))
    else:
        raise TypeError(f"Invalid widget: {widget}")


class QT_Widget(QWidget):
    """
    A QWidget wrapper.
    """

    def __init__(self, **props):
        super().__init__()
        logger.debug(f"Init QT_Widget with props: {props}")

        defult_layout = QVBoxLayout()
        defult_layout.setContentsMargins(0, 0, 0, 0)
        defult_layout.setSpacing(0)
        layout: QLayout = props.pop("layout", defult_layout)

        apply_style_props(self, layout, **props)

        if props.get("ref", None):
            logger.debug(f"Setting ref {self} to {props['ref']}")
            props["ref"].current = self
        if props.get("key", None):
            logger.debug(f"Setting objectName {props['key']} to {self}")
            self.setObjectName(props["key"])
            layout.setObjectName(f"{props['key']}_layout")

        self.setLayout(layout)

    def __repr__(self) -> str:
        return f"<QT_Widget[{self.__class__.__name__}] objectName={self.objectName()}>"


class QT_VBox(QT_Widget):
    def __init__(self, **props):
        props["layout"] = props.get("layout", QVBoxLayout())
        props["spacing"] = props.get("spacing", 0)
        props["margin"] = props.get("margin", (0, 0, 0, 0))
        props["alignment"] = props.get("alignment", Qt.AlignmentFlag.AlignTop)
        super().__init__(**props)


class QT_HBox(QT_Widget):
    def __init__(self, **props):
        props["layout"] = props.get("layout", QHBoxLayout())
        props["spacing"] = props.get("spacing", 0)
        props["margin"] = props.get("margin", (0, 0, 0, 0))
        props["alignment"] = props.get("alignment", Qt.AlignmentFlag.AlignLeft)
        super().__init__(**props)


class QT_ScrollArea(QScrollArea):
    """
    特例, 因为需要用 ScrollArea 包裹内容, 所以这里不继承 QT_Widget
    """

    def __init__(self, **props):
        super().__init__()

        self.contentwidget = QWidget()
        if props.get("key", None):
            self.contentwidget.setObjectName(f"{props['key']}_contentwidget")
        apply_widget_props(self.contentwidget, **props)

        self.contentlayout = props.get("layout", QVBoxLayout())
        props["spacing"] = props.get("spacing", 0)
        props["margin"] = props.get("margin", (0, 0, 0, 0))
        props["alignment"] = props.get("alignment", Qt.AlignmentFlag.AlignTop)
        if props.get("key", None):
            self.contentlayout.setObjectName(f"{props['key']}_contentlayout")
        apply_layout_props(self.contentlayout, **props)
        self.contentwidget.setLayout(self.contentlayout)

        if props.get("key", None):
            self.setObjectName(f"{props['key']}_scrollarea")

        widget_resizable = props.get("widget_resizable", True)
        if callable(widget_resizable):
            create_effect(lambda: self.setWidgetResizable(widget_resizable()))
        else:
            self.setWidgetResizable(widget_resizable)

        self.setWidget(self.contentwidget)

    def layout(self) -> QLayout:
        return self.contentlayout

    def __repr__(self) -> str:
        return f"<QT_Widget[QT_ScrollArea] objectName={self.objectName()}>"


class QT_Button(QT_Widget):
    def __init__(
        self,
        *,
        text,
        on_click: Callable[[None], None] | None = None,
        **props,
    ):
        super().__init__(**props)

        if on_click:
            self.on_click = on_click

        self.button = QPushButton()

        # 不知道为什么这里用 handle_accessor 会报错 wrapped C/C++ object has been deleted
        # handle_accessor(self.button.setText, text, operation="str")
        if callable(text):
            create_effect(lambda: self.button.setText(str(text())))
        else:
            self.button.setText(str(text))

        self.button.clicked.connect(self.on_click)
        if props.get("key", None):
            self.button.setObjectName(f"{props['key']}_button")

        self.layout().addWidget(self.button)

    def on_click(self):
        pass

    def reconnect(self, on_click):
        self.button.clicked.disconnect()
        self.button.clicked.connect(on_click)


class QT_Label(QT_Widget):
    def __init__(self, *, text, **props):
        super().__init__(**props)

        self.label = QLabel()

        # 不知道为什么这里用 handle_accessor 会报错 wrapped C/C++ object has been deleted
        # handle_accessor(self.label.setText, text, operation="str")
        if callable(text):
            create_effect(lambda: self.label.setText(str(text())))
        else:
            self.label.setText(str(text))

        if props.get("key", None):
            self.label.setObjectName(f"{props['key']}_label")

        self.layout().addWidget(self.label)


class QT_Input(QT_Widget):
    def __init__(self, **props):
        super().__init__(**props)

        on_edit = props.get("on_edit", None)
        if on_edit:
            self.on_edit = on_edit

        self.input = QLineEdit()
        self.input.textEdited.connect(self.on_edit)
        if props.get("key", None):
            self.input.setObjectName(f"{props['key']}_input")

        self.layout().addWidget(self.input)

    def on_edit(self):
        pass

    def text(self):
        return self.input.text()
