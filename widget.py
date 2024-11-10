from __future__ import annotations
from typing import Callable
from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLayout,
    QLabel,
    QPushButton,
    QLineEdit,
)
from PyQt6.QtCore import Qt


class QT_Layout(QLayout):
    """
    A type hint for change the name QLayout to QT_Layout.
    """

    pass


def apply_style_kwargs(widget: QT_Widget, layout: QT_Layout, **kwargs):
    for key, value in kwargs.items():
        if key == "margin":
            layout.setContentsMargins(*value)
        elif key == "spacing":
            layout.setSpacing(value)
        elif key == "alignment":
            layout.setAlignment(value)
        elif key == "size_policy":
            layout.setSizeConstraint(value)
        elif key == "alignment":
            layout.setAlignment(value)
        elif key == "qss":
            widget.setStyleSheet(value)
        elif key == "minimum_size":
            widget.setMinimumSize(*value)
        elif key == "maximum_size":
            widget.setMaximumSize(*value)
        elif key == "size":
            widget.setFixedSize(*value)


def add_widget_to_layout(layout: QLayout, widget: QT_Widget | str | int):
    layout.addWidget(create_widget(widget))


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

    def __init__(self, *children, **props):
        super().__init__()

        defult_layout = QVBoxLayout()
        defult_layout.setContentsMargins(0, 0, 0, 0)
        defult_layout.setSpacing(0)
        layout: QLayout = props.pop("layout", defult_layout)

        for widget in children:
            add_widget_to_layout(layout, widget)
        apply_style_kwargs(self, layout, **props)

        if props.get("ref", None):
            props["ref"] = self
        if props.get("key", None):
            self.setObjectName(props["key"])
            layout.setObjectName(f"{props['key']}_layout")

        self.setLayout(layout)

    def __repr__(self) -> str:
        return f"<QT_Widget[{self.__class__.__name__}] objectName={self.objectName()}>"

    def update_props(self, **props):
        apply_style_kwargs(self, self.layout(), **props)


class QT_VBox(QT_Widget):
    def __init__(self, *children, **props):
        props["layout"] = props.get("layout", QVBoxLayout())
        props["spacing"] = props.get("spacing", 0)
        props["margin"] = props.get("margin", (0, 0, 0, 0))
        props["alignment"] = props.get("alignment", Qt.AlignmentFlag.AlignTop)
        super().__init__(*children, **props)


class QT_HBox(QT_Widget):
    def __init__(self, *children, **props):
        props["layout"] = props.get("layout", QHBoxLayout())
        props["spacing"] = props.get("spacing", 0)
        props["margin"] = props.get("margin", (0, 0, 0, 0))
        props["alignment"] = props.get("alignment", Qt.AlignmentFlag.AlignLeft)
        super().__init__(*children, **props)


class QT_Button(QT_Widget):
    def __init__(self, text, on_click: Callable[[None], None] | None = None, **props):
        super().__init__(**props)

        if on_click:
            self.on_click = on_click

        self.button = QPushButton(text=text)
        self.button.clicked.connect(self.on_click)
        if props.get("key", None):
            self.button.setObjectName(f"{props['key']}_button")

        self.layout().addWidget(self.button)

    def on_click(self):
        pass


class QT_Label(QT_Widget):
    def __init__(self, text, **props):
        super().__init__(**props)

        self.label = QLabel(text=text)
        if props.get("key", None):
            self.label.setObjectName(f"{props['key']}_label")

        self.layout().addWidget(self.label)


class QT_Input(QT_Widget):
    def __init__(self, **props):
        super().__init__(**props)

        self.input = QLineEdit()
        if props.get("key", None):
            self.input.setObjectName(f"{props['key']}_input")

        self.layout().addWidget(self.input)
