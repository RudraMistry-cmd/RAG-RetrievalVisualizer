"""
Serializes inference work (embeddings, reranking, LLM generation) and enforces a
cooldown between jobs to avoid overloading limited VRAM when multiple users
share the backend.
"""
import threading
import time


class InferenceQueue:
    def __init__(self, cooldown_seconds: float = 3.0):
        self.cooldown_seconds = cooldown_seconds
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)
        self._busy = False
        self._last_completed = 0.0

    def run(self, fn, *args, **kwargs):
        self._acquire()
        try:
            return fn(*args, **kwargs)
        finally:
            self._release()

    def _acquire(self):
        with self._cond:
            while True:
                now = time.time()
                wait_for_cooldown = (self._last_completed + self.cooldown_seconds) - now
                if not self._busy and wait_for_cooldown <= 0:
                    self._busy = True
                    return
                timeout = 0.25
                if not self._busy and wait_for_cooldown > 0:
                    timeout = min(wait_for_cooldown, 1.0)
                self._cond.wait(timeout=timeout)

    def _release(self):
        with self._cond:
            self._last_completed = time.time()
            self._busy = False
            self._cond.notify_all()


inference_queue = InferenceQueue(cooldown_seconds=3.0)
