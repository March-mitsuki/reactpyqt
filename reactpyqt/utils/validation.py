from __future__ import annotations
import threading

# fmt: off
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core import ReactiveNode
# fmt: on


def is_main_thread():
    """
    Check if the current thread is the main thread

    :return: bool
    """
    return threading.get_ident() == threading.main_thread().ident


def is_component_node(obj: ReactiveNode) -> bool:
    """
    Check if the object is a component node

    :param obj: ReactiveNode
    """
    return obj.component is not None and obj.tag is None and obj.control_flow is None


def is_virtual_widget_node(obj: ReactiveNode) -> bool:
    """
    Check if the object is a component node

    :param obj: ReactiveNode
    """
    return obj.component is None and obj.tag is not None and obj.control_flow is None


def is_control_flow_node(obj: ReactiveNode) -> bool:
    """
    Check if the object is a component node

    :param obj: ReactiveNode
    """
    return obj.component is None and obj.tag is None and obj.control_flow is not None
