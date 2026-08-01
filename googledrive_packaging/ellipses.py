import itertools
import sys
import threading
import time

'''
Adds animated ellipses ... to the end of any text like print. Auto stops on any new print statement.
'''
class ellipses:
    _last = None
    _lock = threading.RLock()
    _output_lock = threading.Lock()
    _stdouterr_patched = False
    _original_stdout = sys.stdout
    _write_state = threading.local()

    class _SpinnerStream:
        def __init__(self, wrapped):
            self._wrapped = wrapped

        def write(self, s):
            # Ignore writes made by the spinner thread itself.
            if not getattr(ellipses._write_state, "spinner_write", False):
                if s.strip():
                    ellipses.stop()

            return self._wrapped.write(s)

        def flush(self):
            return self._wrapped.flush()

        def __getattr__(self, name):
            return getattr(self._wrapped, name)

    @classmethod
    def _patch_stdout(cls):
        if not cls._stdouterr_patched:
            sys.stdout = cls._SpinnerStream(sys.stdout)
            sys.stderr = cls._SpinnerStream(sys.stderr)
            cls._stdouterr_patched = True

    def __init__(self, text="Working", delay=0.5, frames=None):
        type(self)._patch_stdout()

        self.text = text
        self.delay = delay
        self.frames = frames or [".", "..", "..."]

        self._running = False
        self._thread = None
        self._width = 0

        with type(self)._lock:
            if type(self)._last is not None:
                type(self)._last._stop()

            type(self)._last = self
            self._start()

    def _write(self, line):
        self._width = max(self._width, len(line))

        with type(self)._output_lock:
            type(self)._write_state.spinner_write = True

            try:
                sys.stdout.write(f"\r{line:<{self._width}}")
                sys.stdout.flush()
            finally:
                type(self)._write_state.spinner_write = False

    def _clear(self):
        with type(self)._output_lock:
            type(self)._write_state.spinner_write = True

            try:
                sys.stdout.write("\r" + " " * self._width + "\r")
                sys.stdout.flush()
            finally:
                type(self)._write_state.spinner_write = False

    def _spin(self):
        for frame in itertools.cycle(self.frames):
            if not self._running:
                break

            self._write(f"{self.text} {frame}")
            time.sleep(self.delay)

        self._clear()

    def _start(self):
        self._running = True
        self._thread = threading.Thread(
            target=self._spin,
            daemon=True
        )
        self._thread.start()

    def _stop(self):
        if not self._running:
            return

        self._running = False

        if (
            self._thread is not None
            and self._thread is not threading.current_thread()
        ):
            self._thread.join()

    @classmethod
    def stop(cls):
        with cls._lock:
            spinner = cls._last
            cls._last = None

        if spinner is not None:
            spinner._stop()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self._stop()

        with type(self)._lock:
            if type(self)._last is self:
                type(self)._last = None

        return False