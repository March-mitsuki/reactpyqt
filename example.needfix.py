from reactpyqt.core import (
    Component,
    ControlFlow,
    MainWindow,
    HBox,
    VBox,
    Button,
    Label,
    Input,
    ScrollArea,
    For,
    Switch,
    Case,
)
from reactpyqt.reactive import create_signal, create_effect
from loguru import logger

page, set_page = create_signal("home")
todo, set_todo = create_signal(["Hello", "World"])
create_effect(lambda: logger.info(f"Todo: {todo()}"))


class Router(Component):
    def render(self):
        return Switch(
            condition=page,
            cases=[
                Case(
                    when=lambda page: page == "home",
                    render=Home(),
                ),
                Case(
                    when=lambda page: page == "add-todo",
                    render=AddTodo(),
                ),
            ],
            fallback=Label("404"),
        )


class AddTodo(Component):
    def render(self):
        logger.info("Rendering AddTodo")
        todo_name, set_todo_name = create_signal("")
        create_effect(lambda: logger.info(f"todo_name changed {todo_name()}"))

        create_effect(lambda: logger.info(f"trace todo in AddTodo: {todo()}"))

        return VBox(
            Label("Todo Name"),
            Input(on_edit=set_todo_name),
            Button(
                "Add Todo",
                on_click=lambda: ControlFlow(
                    set_todo(todo() + [todo_name]),
                    set_page("home"),
                ),
            ),
            Button("Back", on_click=lambda: set_page("home")),
        )


class Home(Component):
    def render(self):
        return VBox(
            Label("Home"),
            HBox(
                Button("Add Todo", on_click=lambda: set_page("add-todo")),
                Button(
                    "Add Todo Direct",
                    on_click=lambda: set_todo(todo() + [f"New {len(todo())}"]),
                ),
            ),
            ScrollArea(
                For(
                    each=todo,
                    map_fn=self.render_todo_item,
                    fallback=Label("No todos"),
                ),
            ),
        )

    def render_todo_item(self, item, idx):
        logger.info(f"Rendering todo item: {item}")
        return Label(item)


class App(Component):
    def render(self):
        return VBox(Router(), key="app-wrapper")


if __name__ == "__main__":
    import sys

    logger.remove()
    logger.add(sys.stderr, level="INFO")

    app = MainWindow(App())
    app.start()
