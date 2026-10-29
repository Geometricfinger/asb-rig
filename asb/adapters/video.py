"""Video camera adapter (C2): a file path or a stream URL (HLS/RTSP/MJPEG/HTTP) read with
OpenCV (Apache-2.0; the opencv-python wheel ships FFmpeg as an LGPL shared library, not
linked into this package). Imported lazily: OpenCV stays an optional `[hw]` dependency.

Honest limits: an ordinary visible-light video has **no IR LED on/off pair**, so the
"nir_pair" it emits uses the same frame for on and off (quality 0.3, like the Pi camera
without its LED). Lens-glint differencing (A1) therefore cannot fire from this source;
A2 (saturated spots) is measured on visible light, not near-IR. Frames live in RAM only
and are never written (privacy guard: no full frames of people are persisted)."""
from __future__ import annotations
import time
from typing import Any

import numpy as np

from ..schema import Health
from .base import AdapterBase


class DriverUnavailable(RuntimeError):
    pass


class VideoAdapter(AdapterBase):
    id, bus, caps, units = "video", "net", {"nir_pair", "motion"}, "dn"
    SOURCE = "visible_video_no_ir_led"

    def __init__(self, url: str | None = None, size: tuple[int, int] = (320, 180), step_s: float = 1.0,
                 adapter_id: str | None = None):
        super().__init__(adapter_id)
        self.url, self.size, self.step_s = url, size, step_s
        self._cap: Any = None
        self._prev: np.ndarray | None = None

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        self.url = cfg.get("url", self.url)
        if not self.url:
            raise ValueError("video adapter needs a file path or URL")
        try:
            import cv2  # type: ignore
        except ImportError as e:
            raise DriverUnavailable("pip install opencv-python-headless") from e
        self._cv2 = cv2
        self._cap = cv2.VideoCapture(self.url, cv2.CAP_FFMPEG)
        if not self._cap.isOpened():
            raise DriverUnavailable(f"cannot open video source {self.url}")
        fps = self._cap.get(cv2.CAP_PROP_FPS) or 0.0
        self.fps = fps if 0 < fps < 240 else 15.0
        self._prev = None

    def read(self, timeout_s: float):
        assert self._cap is not None, "open() first"
        cv2 = self._cv2
        # advance ~step_s of video per step: grab (decode-skip) frames, then retrieve the last one
        for _ in range(max(0, int(self.fps * self.step_s) - 1)):
            if not self._cap.grab():
                break
        ok, frame = self._cap.read()
        if not ok or frame is None:
            self.set_health(Health.DEGRADED, "no frame (stream ended or stalled)")
            return None
        gray = cv2.cvtColor(cv2.resize(frame, self.size, interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        jerk = 0.0 if self._prev is None else float(np.clip(np.abs(gray.astype(np.int16) - self._prev).mean() / 255 * 10, 0, 1))
        self._prev = gray.astype(np.int16)
        self.set_health(Health.OK, "")
        return self._sample({"on": gray, "off": gray, "jerk": jerk, "source": self.SOURCE,
                             "frame_mean": float(gray.mean()), "t_capture": time.time()}, quality=0.3)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
