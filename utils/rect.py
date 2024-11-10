from PyQt6.QtCore import QRect


def zoom_rect(rect: QRect, factor):
    """中心缩放 QRect"""
    width = int(rect.width() * factor)
    height = int(rect.height() * factor)
    x = int(rect.x() - (width - rect.width()) / 2)
    y = int(rect.y() - (height - rect.height()) / 2)
    return QRect(x, y, width, height)
