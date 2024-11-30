from reactpyqt.core import (
    Component,
    Switch,
    Case,
    For,
    HBox,
    VBox,
    ScrollArea,
    Label,
    Button,
    Input,
    MainWindow,
)
from reactpyqt.reactive import (
    create_signal,
    create_effect,
    with_text,
)
from reactpyqt.timer import set_timeout, set_interval


###################### Logging setup #######################
from loguru import logger
import sys

logger.remove()
logger.add(sys.stdout, level="INFO")
###################### Logging setup #######################


class Nav(Component):
    def render(self):
        is_logged_in = self.props.get("is_logged_in")

        return Switch(
            key="nav-switch",
            condition=is_logged_in,
            cases=[
                Case(
                    when=lambda is_logged_in: is_logged_in,
                    render=HBox(
                        Label("Home", key="nav-home"),
                        Label("Dashboard", key="nav-dashboard"),
                        Label("Logout", key="nav-logout"),
                        key="nav-logged-in-wrapper",
                        qss="background-color: 'green';",
                        spacing=10,
                    ),
                    key="nav-logged-in-case",
                ),
                Case(
                    when=lambda is_logged_in: not is_logged_in,
                    render=HBox(
                        Label("Home", key="nav-home"),
                        Label("Login", key="nav-login"),
                        Label("Register", key="nav-register"),
                        key="nav-logged-out-wrapper",
                        qss="background-color: 'red';",
                        spacing=10,
                    ),
                    key="nav-logged-out-case",
                ),
            ],
            fallback=Label("No Nav", key="nav-fallback"),
        )


class TodoItem(Component):
    def render(self):
        item = self.props.get("item")
        remove_fn = self.props.get("remove_fn")

        nested_items, set_nested_items = create_signal(
            ["Nested item in todo 1", "Nested item in todo 2"]
        )
        set_timeout(
            lambda: set_nested_items(lambda prev: prev + ["Nested item in todo 3"]), 5
        )

        return HBox(
            Label("Item: ", key=f"todo-item-title-{item}"),
            Label(item, key=item),
            VBox(
                For(
                    each=nested_items,
                    map_fn=lambda nested_item, idx: Label(
                        nested_item,
                        key=f"nested-item-{nested_item}",
                    ),
                    key=f"nested-item-for-{item}",
                ),
            ),
            Button(
                "Delete",
                key=f"todo-item-delete-{item}",
                on_click=lambda: remove_fn(self.props.get("idx")),
            ),
            key=f"todo-item-hbox-{item}",
        )


class App(Component):
    def __init__(self):
        self.props = {
            "key": "app-component",
        }

    def render(self):
        is_logged_in, set_is_logged_in = create_signal(False)
        set_timeout(lambda: set_is_logged_in(True), 5)

        todo, set_todo = create_signal(["First Render", "Buy something"])
        create_effect(lambda: logger.debug("todo changed: {}", todo()))

        count, set_count = create_signal(0)
        set_interval(lambda: set_count(count() + 1), 1)

        def add_todo():
            set_todo(lambda prev: [*prev, f"New Todo {len(prev)}"])

        def remove_todo(idx):
            set_todo(lambda prev: prev[:idx] + prev[idx + 1 :])

        def render_list(item, idx):
            return TodoItem(
                item=item,
                idx=idx,
                remove_fn=remove_todo,
                key=f"todo-item-component-{item}",
            )

        qss_bg, set_qss_bg = create_signal("background-color: 'yellow';")
        set_timeout(lambda: set_qss_bg("background-color: 'orange';"), 5)

        return VBox(
            Label(with_text("Login state: {}", is_logged_in), key="login-state"),
            Nav(is_logged_in=is_logged_in, key="nav-component"),
            Label(
                "Welcome to ReactivePyQt",
                key="welcome-label",
                qss=qss_bg,
            ),
            Label(with_text("Count {}", count), key="count"),
            Input(key="input"),
            VBox(
                Label("Todo List", key="todo-label"),
                ScrollArea(
                    For(
                        each=todo,
                        map_fn=render_list,
                        fallback=Label("No todo items", key="no-todo"),
                        key="todo-list-for",
                    ),
                    key="scroll-area",
                ),
                spacing=5,
                key="todo-list-wrapper",
            ),
            Button("Add Todo", key="add-todo", on_click=add_todo),
            key="app-wrapper",
        )


main_window = MainWindow(App())
main_window.start()
