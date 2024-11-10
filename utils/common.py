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
