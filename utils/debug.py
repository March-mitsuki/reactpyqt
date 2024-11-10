from PyQt6.QtWidgets import QLayout


def print_layout_contents(layout: QLayout, level=0):
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
            print(
                f"{indent}Widget-layout: {widget_layout.objectName()} ({type(widget.layout()).__name__})"
            )
            print_layout_contents(widget.layout(), level + 1)

        if sub_layout:
            # 如果是子布局，递归调用
            print(
                f"{indent}Layout: {widget_layout.objectName()} {type(sub_layout).__name__}"
            )
            print_layout_contents(sub_layout, level + 1)
