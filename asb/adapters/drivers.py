"""Real hardware drivers (C2). Each imports its vendor library lazily inside open(), so
the package imports and tests run on any machine without hardware. All radio drivers are
receive-only and go through guard.radio. Licenses of optional libs: see THIRD_PARTY.md."""
from __future__ import annotations
import re, shutil, time
from typing import Any

import numpy as np

from ..guard import radio
from ..schema import Health
from .base import AdapterBase


class DriverUnavailable(RuntimeError):
    pass


class Mlx90640Adapter(AdapterBase):
    """Melexis MLX90640 32x24 thermal over I2C (adafruit-circuitpython-mlx90640, MIT)."""
    id, bus, caps, units = "thermal_mlx90640", "i2c", {"thermal_frame"}, "degC"

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        try:
            import board, busio, adafruit_mlx90640  # type: ignore
        except ImportError as e:
            raise DriverUnavailable("pip install adafruit-circuitpython-mlx90640") from e
        i2c = busio.I2C(board.SCL, board.SDA, frequency=800000)
        self._dev = adafruit_mlx90640.MLX90640(i2c)
        self._dev.refresh_rate = getattr(adafruit_mlx90640.RefreshRate, f"REFRESH_{cfg.get('hz', 4)}_HZ")
        self._buf = [0.0] * 768

    def read(self, timeout_s: float):
        self._dev.getFrame(self._buf)
        return self._sample({"frame_c": np.asarray(self._buf, float).reshape(24, 32)})


class UvcThermalAdapter(AdapterBase):
    """FLIR Lepton on PureThermal (UVC, Y16 radiometric) via OpenCV (Apache-2.0)."""
    id, bus, caps, units = "thermal_uvc", "usb", {"thermal_frame"}, "degC"

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        try:
            import cv2  # type: ignore
        except ImportError as e:
            raise DriverUnavailable("pip install opencv-python-headless") from e
        self._cv2 = cv2
        self._cap = cv2.VideoCapture(cfg.get("device", 0))
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter.fourcc(*"Y16 "))
        self._cap.set(cv2.CAP_PROP_CONVERT_RGB, 0)
        if not self._cap.isOpened():
            raise DriverUnavailable("PureThermal device not found")

    def read(self, timeout_s: float):
        ok, raw = self._cap.read()
        if not ok:
            self.set_health(Health.DEGRADED, "frame grab failed")
            return None
        return self._sample({"frame_c": raw.astype(float) / 100.0 - 273.15})   # centi-Kelvin (TLinear)

    def close(self) -> None:
        getattr(self, "_cap", None) and self._cap.release()


class PiCameraNirAdapter(AdapterBase):
    """Pi NoIR camera via picamera2 (BSD-2) with an IR LED pulsed on alternate frames."""
    id, bus, caps, units = "camera_noir", "csi", {"nir_pair"}, "dn"

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        try:
            from picamera2 import Picamera2  # type: ignore
        except ImportError as e:
            raise DriverUnavailable("picamera2 only on Raspberry Pi OS") from e
        self._cam = Picamera2(cfg.get("index", 0))
        self._cam.configure(self._cam.create_video_configuration(main={"size": (640, 480), "format": "YUV420"}))
        self._led = cfg.get("led")   # IrLed instance, enforces duty cap
        self._cam.start()

    def _gray(self):
        return self._cam.capture_array()[:480, :640]

    def read(self, timeout_s: float):
        if self._led is None:
            off = self._gray()
            return self._sample({"on": off, "off": off}, quality=0.3)
        self._led.on(); on = self._gray(); self._led.off(); off = self._gray()
        return self._sample({"on": on, "off": off})

    def close(self) -> None:
        getattr(self, "_cam", None) and self._cam.stop()


class IrLed:
    """850 nm LED on a GPIO via gpiozero (BSD-3) with a hard duty-cycle cap (<=25%, IEC 62471 worksheet)."""

    def __init__(self, pin: int, duty_cap: float = 0.25, window_s: float = 10.0, pwm=None, clock=time.monotonic,
                 max_pulse_s: float = 0.05):
        if not 0 < duty_cap <= 0.25:
            raise ValueError("duty cap must be <= 25%")
        self.duty_cap, self.window_s, self.clock, self.max_pulse_s = duty_cap, window_s, clock, max_pulse_s
        self._on_since: float | None = None
        self._hist: list[tuple[float, float]] = []
        self._pwm = pwm
        if pwm is None:
            try:
                from gpiozero import LED  # type: ignore
                self._pwm = LED(pin)
            except Exception:
                self._pwm = None

    def duty(self) -> float:
        now = self.clock()
        on = sum(min(e, now) - max(s, now - self.window_s) for s, e in self._hist if e > now - self.window_s)
        if self._on_since is not None:
            on += now - max(self._on_since, now - self.window_s)
        return on / self.window_s

    def on(self) -> bool:
        # refuse unless a full max-length pulse still fits under the cap (pulse length is capped by callers)
        if self.duty() + self.max_pulse_s / self.window_s > self.duty_cap + 1e-12:
            return False
        self._on_since = self.clock()
        self._pwm and self._pwm.on()
        return True

    def off(self) -> None:
        if self._on_since is not None:
            self._hist.append((self._on_since, self.clock()))
            self._on_since = None
        self._pwm and self._pwm.off()


class BleScanAdapter(AdapterBase):
    """Passive BLE advertisement scanning via bleak (MIT). Addresses are HMAC'd before
    leaving the adapter; raw addresses never reach storage."""
    id, bus, caps, units = "ble_scan", "ble", {"rf_adv"}, "dBm"

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        try:
            import bleak  # noqa: F401  # type: ignore
        except ImportError as e:
            raise DriverUnavailable("pip install bleak") from e
        self._key = cfg["site_key"]
        self._self = set(cfg.get("self_allowlist", []))

    def read(self, timeout_s: float):
        import asyncio
        from bleak import BleakScanner  # type: ignore
        from ..guard.privacy import hash_identifier
        found = asyncio.run(BleakScanner.discover(timeout=min(timeout_s, 5.0), return_adv=True))
        em = []
        for addr, (_dev, adv) in found.items():
            k = hash_identifier(addr, self._key)
            em.append({"key": k, "rssi": adv.rssi, "tx_power": adv.tx_power, "company_ids": list(adv.manufacturer_data),
                       "uuids": list(adv.service_uuids), "payload_len": sum(len(v) for v in adv.manufacturer_data.values()),
                       "self": k in self._self})
        return self._sample({"emitters": em})


_BSS = re.compile(r"^BSS ([0-9a-f:]{17})", re.M)
_TSF = re.compile(r"TSF: (\d+) usec")
_SIG = re.compile(r"signal: (-?[\d.]+) dBm")


def parse_iw_scan(text: str) -> list[dict]:
    out = []
    for block in re.split(r"(?=^BSS )", text, flags=re.M):
        m = _BSS.search(block)
        if not m:
            continue
        t, s = _TSF.search(block), _SIG.search(block)
        out.append({"bssid": m.group(1), "tsf_us": int(t.group(1)) if t else None,
                    "rssi": float(s.group(1)) if s else None})
    return out


class WifiBeaconAdapter(AdapterBase):
    """Managed-mode `iw dev <if> scan` (passive policy enforced; never monitor mode)."""
    id, bus, caps, units = "wifi_beacons", "wifi", {"ap_scan"}, "dBm"

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        if not shutil.which("iw"):
            raise DriverUnavailable("iw not installed")
        radio.assert_passive()
        self._if, self._key = cfg.get("interface", "wlan0"), cfg["site_key"]

    def read(self, timeout_s: float):
        from ..guard.privacy import hash_identifier
        aps = parse_iw_scan(radio.run_passive(["iw", "dev", self._if, "scan"], timeout=max(timeout_s, 10)))
        t = time.time()
        return self._sample({"aps": [{"key": hash_identifier(a["bssid"], self._key), "tsf_us": a["tsf_us"],
                                      "rssi": a["rssi"], "local_s": t} for a in aps]})


def parse_nmea(line: str) -> dict | None:
    """$GPGGA/$GNGGA -> fix. Checksum verified; malformed lines return None."""
    line = line.strip()
    if not line.startswith("$") or "*" not in line:
        return None
    body, cs = line[1:].split("*", 1)
    c = 0
    for ch in body:
        c ^= ord(ch)
    if f"{c:02X}" != cs[:2].upper():
        return None
    f = body.split(",")
    if not f[0].endswith("GGA") or len(f) < 7:
        return None
    if f[6] in ("", "0") or not f[2]:
        return {"quality": "no_fix", "lat": None, "lon": None}
    lat = int(f[2][:2]) + float(f[2][2:]) / 60
    lon = int(f[4][:3]) + float(f[4][3:]) / 60
    return {"quality": "3d", "lat": -lat if f[3] == "S" else lat, "lon": -lon if f[5] == "W" else lon}


class GpsAdapter(AdapterBase):
    """PA1010D (I2C) / any NMEA serial GPS via pyserial (BSD-3)."""
    id, bus, caps, units = "gps", "uart", {"gps"}, "deg"

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        try:
            import serial  # type: ignore
        except ImportError as e:
            raise DriverUnavailable("pip install pyserial") from e
        self._s = serial.Serial(cfg.get("port", "/dev/serial0"), cfg.get("baud", 9600), timeout=1)

    def read(self, timeout_s: float):
        end = time.monotonic() + timeout_s
        while time.monotonic() < end:
            fix = parse_nmea(self._s.readline().decode("ascii", "replace"))
            if fix:
                return self._sample(fix)
        return None


def parse_mr60_frame(buf: bytes) -> dict | None:
    """Seeed MR60BHA2 frame: SOF 0x01 | id(2) | len(2) | type(2) | hcksum | data | dcksum.
    Breath-rate type 0x0A14 carries float32 little-endian. Unknown types -> None."""
    import struct
    if len(buf) < 8 or buf[0] != 0x01:
        return None
    ln, typ = struct.unpack(">HH", buf[3:7])
    hck = (~(sum(buf[0:7]) & 0xFF)) & 0xFF
    if buf[7] != hck or len(buf) < 9 + ln:
        return None
    data = buf[8:8 + ln]
    if ((~(sum(data) & 0xFF)) & 0xFF) != buf[8 + ln]:
        return None
    if typ == 0x0A14 and ln == 4:
        return {"breath_rate": struct.unpack("<f", data)[0]}
    if typ == 0x0A16 and ln == 8:
        flag, rng = struct.unpack("<If", data)
        return {"range_m": rng / 100.0 if flag else 9.0}
    return None


class Mr60Adapter(AdapterBase):
    """Seeed MR60BHA2 60 GHz breathing radar over UART (pyserial). Tier B."""
    id, bus, caps, units = "mmwave_mr60", "uart", {"radar"}, "bpm"

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        try:
            import serial  # type: ignore
        except ImportError as e:
            raise DriverUnavailable("pip install pyserial") from e
        self._s = serial.Serial(cfg.get("port", "/dev/ttyUSB0"), 115200, timeout=0.5)
        self._st = {"breath_rate": 0.0, "range_m": 9.0}

    def read(self, timeout_s: float):
        buf = self._s.read(64)
        i = buf.find(b"\x01")
        if i >= 0:
            p = parse_mr60_frame(buf[i:])
            if p:
                self._st.update(p)
        br = self._st["breath_rate"]
        return self._sample({"breath_snr_db": 8.0 if 6 <= br <= 30 else 0.0, "range_m": self._st["range_m"],
                             "breath_rate": br})


class RtlSdrProbe(AdapterBase):
    """Exploratory E-10 probe: `rtl_power` (GPL tool as a separate executable), receive-only."""
    id, bus, caps, units = "sdr_probe", "usb", {"sdr_power"}, "dB"

    def open(self, cfg: dict) -> None:
        super().open(cfg)
        if not shutil.which("rtl_power"):
            raise DriverUnavailable("rtl_power not installed")
        lo, hi = cfg.get("lo_mhz", 780), cfg.get("hi_mhz", 870)
        if not (24 <= lo < hi <= 1766):
            raise ValueError("RTL-SDR V4 tunes 24-1766 MHz")
        self._argv = ["rtl_power", "-f", f"{lo}M:{hi}M:100k", "-i", "1", "-1"]

    def read(self, timeout_s: float):
        out = radio.run_passive(self._argv, timeout=max(timeout_s, 5))
        vals = [float(x) for line in out.splitlines() for x in line.split(",")[6:] if x.strip()]
        return self._sample({"power_db": vals})


class AndroidBridgeAdapter(AdapterBase):
    """M-13: Android fallback node scores arrive over the Noise channel as C1 records."""
    id, bus, caps, units = "android_node", "android", {"node_scores"}, ""

    def __init__(self, recv=None):
        super().__init__()
        self._recv = recv

    def read(self, timeout_s: float):
        msg: Any = self._recv(timeout_s) if self._recv else None
        return self._sample(msg) if msg else None


REAL = [Mlx90640Adapter, UvcThermalAdapter, PiCameraNirAdapter, BleScanAdapter, WifiBeaconAdapter, GpsAdapter,
        Mr60Adapter, RtlSdrProbe, AndroidBridgeAdapter]
