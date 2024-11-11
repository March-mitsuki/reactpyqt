from PyQt6.QtCore import QRunnable, QThreadPool, pyqtSignal, pyqtSlot, QObject

from .globalvar import __intervals__


class Timeout(QRunnable):
    """
    Sleep for a while and emit a signal when timeout.

    Attributes:
        self.timeout: int, timeout in seconds
    """

    class TimtoutSignal(QObject):
        timeout = pyqtSignal()

    def __init__(self, timeout: int):
        super().__init__()
        self.timeout = timeout
        self.signal = self.TimtoutSignal()

    @pyqtSlot()
    def run(self):
        import time

        time.sleep(self.timeout)
        try:
            self.signal.timeout.emit()
        except RuntimeError:
            pass


def set_timeout(func, sec):
    """
    Like JavaScript's setTimeout.

    Set a timeout to run a function after a certain amount of time.

    :param func: function to run
    :param sec: int, seconds to wait
    """
    timeout = Timeout(sec)
    timeout.signal.timeout.connect(func)
    QThreadPool.globalInstance().start(timeout)


class Interval(QRunnable):
    """
    Run a function at regular intervals and emit a signal each time.

    Attributes:
        self.interval: int, interval in seconds
    """

    class IntervalSignal(QObject):
        tick = pyqtSignal()

    def __init__(self, interval: int):
        super().__init__()
        self.interval = interval
        self.signal = self.IntervalSignal()
        self._running = True

    @pyqtSlot()
    def run(self):
        import time

        while self._running:
            time.sleep(self.interval)
            try:
                self.signal.tick.emit()
            except RuntimeError:
                pass

    def stop(self):
        self._running = False


def set_interval(func, sec):
    """
    Like JavaScript's setInterval.

    Run a function at regular intervals.
    Return the interval instance to allow stopping it later.

    Will start immediately.
    Will stop when the application exits.

    :param func: function to run
    :param sec: int, interval in seconds

    :return: Interval
    """

    global __intervals__
    interval = Interval(sec)
    __intervals__.append(interval)
    interval.signal.tick.connect(func)
    QThreadPool.globalInstance().start(interval)
    return interval  # Return the interval instance to allow stopping it later
