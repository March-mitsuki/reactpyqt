from __future__ import annotations
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
        layout = props.pop("layout", defult_layout)

        self.chiyo_children = []
        for widget in children:
            add_widget_to_layout(layout, widget)
        apply_style_kwargs(self, layout, **props)

        if props.get("ref", None):
            props["ref"] = self
        if props.get("key", None):
            self.setObjectName(props["key"])

        self.setLayout(layout)

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
    def __init__(self, text, **props):
        super().__init__(**props)

        self.button = QPushButton(text=text)
        self.button.clicked.connect(self.clicked)
        self.layout().addWidget(self.button)

    def clicked(self):
        print("Button clicked")


class QT_Label(QT_Widget):
    def __init__(self, text, **props):
        super().__init__(**props)

        self.label = QLabel(text=text)
        self.layout().addWidget(self.label)


class QT_Input(QT_Widget):
    def __init__(self, **props):
        super().__init__(**props)

        self.input = QLineEdit()
        self.layout().addWidget(self.input)
