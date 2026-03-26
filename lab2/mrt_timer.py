import time


class Timer:
    """
    Simple retransmission timer for the MRT protocol.
    Tracks whether a timeout has occurred since the last
    start/reset.
    """

    def __init__(self, timeout=0.5):
        """
        Create a new timer with the given timeout duration.

        arguments:
        timeout -- duration in seconds before the timer expires
        """
        self.timeout = timeout
        self._start_time = 0
        self._running = False

    def start(self):
        """
        Start or restart the timer from now.
        """
        self._start_time = time.time()
        self._running = True

    def stop(self):
        """
        Stop the timer.
        """
        self._running = False

    def reset(self):
        """
        Reset the timer start time to now (same as start).
        """
        self._start_time = time.time()

    def is_expired(self):
        """
        Check if the timer is running and has exceeded the
        timeout duration.

        return:
        bool -- True if timed out
        """
        if not self._running:
            return False
        return time.time() - self._start_time > self.timeout

    def is_running(self):
        """
        Check if the timer is currently running.

        return:
        bool -- True if running
        """
        return self._running
