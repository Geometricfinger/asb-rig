"""BLE GATT transport for Noise channel frames (pod = GATT server/peripheral, phone = client).

One O Iris GATT service with two characteristics:
  RX (phone -> pod): write-without-response;  TX (pod -> phone): notify.
A Noise frame (<= 65,539 bytes incl. the 4-byte rekey-generation header) is cut into ATT-sized
segments. Segment = seq (1 byte, wraps) | flags (1 byte: 0x01 first, 0x02 last) | [total length,
4 bytes BE, first segment only] | payload. The receiver checks sequence continuity and length,
and drops a partial frame on any gap (the Noise layer then rejects the next frame cleanly).
Everything carried here is already Noise-encrypted; this layer adds no secrets and trusts nothing.

Hardware: the GATT server adapter needs a BLE radio (`bless`, MIT, optional `hw` extra) and is
not exercised by tests; the segmenting, reassembly and the full Noise-over-segments path are
tested over an in-memory loopback link with realistic MTUs. Byte format shared with
android/core BleFraming.kt via tests/vectors/ble_framing.json."""
from __future__ import annotations
import queue, struct, threading
from dataclasses import dataclass, field
from typing import Callable, Protocol

SERVICE_UUID = "6f697269-7300-4c69-6e6b-000000000001"   # "oiris" link service
RX_CHAR_UUID = "6f697269-7300-4c69-6e6b-000000000002"   # phone -> pod (write without response)
TX_CHAR_UUID = "6f697269-7300-4c69-6e6b-000000000003"   # pod -> phone (notify)
FIRST, LAST = 0x01, 0x02
MAX_FRAME = 65_535 + 4
DEFAULT_MTU = 247          # ATT MTU requested by the phone; payload per write = MTU - 3


class FramingError(ValueError):
    pass


def segment(frame: bytes, mtu: int, seq0: int = 0) -> list[bytes]:
    if not 0 < len(frame) <= MAX_FRAME:
        raise FramingError("frame size out of range")
    room = mtu - 3 - 2
    if room < 8:
        raise FramingError("MTU too small")
    out: list[bytes] = []
    pos, seq = 0, seq0
    first_room = room - 4
    while pos < len(frame) or not out:
        first = not out
        n = first_room if first else room
        chunk = frame[pos:pos + n]
        pos += len(chunk)
        flags = (FIRST if first else 0) | (LAST if pos >= len(frame) else 0)
        hdr = bytes([seq & 0xFF, flags]) + (struct.pack(">I", len(frame)) if first else b"")
        out.append(hdr + chunk)
        seq += 1
    return out


@dataclass
class Desegmenter:
    """Feed segments in arrival order; returns a whole frame when the last segment arrives."""
    expect_seq: int | None = None
    buf: bytearray = field(default_factory=bytearray)
    total: int = 0
    active: bool = False
    dropped: int = 0

    def _reset(self) -> None:
        self.buf.clear(); self.total = 0; self.active = False

    def feed(self, seg: bytes) -> bytes | None:
        if len(seg) < 2:
            self.dropped += 1; self._reset(); return None
        seq, flags, body = seg[0], seg[1], seg[2:]
        if self.expect_seq is not None and seq != self.expect_seq:
            if self.active:
                self.dropped += 1
            self._reset()
        self.expect_seq = (seq + 1) & 0xFF
        if flags & FIRST:
            if self.active:
                self.dropped += 1
            self._reset()
            if len(body) < 4:
                self.dropped += 1; return None
            self.total = struct.unpack(">I", body[:4])[0]
            if not 0 < self.total <= MAX_FRAME:
                self.dropped += 1; return None
            body = body[4:]
            self.active = True
        elif not self.active:
            return None                          # mid-frame segment after a drop: ignore
        self.buf += body
        if len(self.buf) > self.total:
            self.dropped += 1; self._reset(); return None
        if flags & LAST:
            if len(self.buf) != self.total:
                self.dropped += 1; self._reset(); return None
            out = bytes(self.buf); self._reset()
            return out
        return None


class FrameTransport(Protocol):
    def send(self, frame: bytes) -> None: ...
    def receive(self, timeout_s: float) -> bytes | None: ...


class SegmentedLink:
    """FrameTransport over any segment pipe (`write_segment` callable + `on_segment` feed)."""

    def __init__(self, write_segment: Callable[[bytes], None], mtu: int = DEFAULT_MTU):
        self.write_segment, self.mtu = write_segment, mtu
        self._seq = 0
        self._rx = Desegmenter()
        self._q: queue.Queue[bytes] = queue.Queue()
        self._lock = threading.Lock()

    def send(self, frame: bytes) -> None:
        with self._lock:
            segs = segment(frame, self.mtu, self._seq)
            self._seq = (self._seq + len(segs)) & 0xFF
            for s in segs:
                self.write_segment(s)

    def on_segment(self, seg: bytes) -> None:
        f = self._rx.feed(seg)
        if f is not None:
            self._q.put(f)

    def receive(self, timeout_s: float) -> bytes | None:
        try:
            return self._q.get(timeout=timeout_s)
        except queue.Empty:
            return None

    @property
    def dropped(self) -> int:
        return self._rx.dropped


def loopback_pair(mtu: int = DEFAULT_MTU, tamper: Callable[[bytes], bytes | None] | None = None) -> tuple[SegmentedLink, SegmentedLink]:
    """Two linked endpoints (phone, pod) in memory. `tamper` may rewrite or drop (None) segments."""
    a: SegmentedLink
    b: SegmentedLink

    def a_to_b(seg: bytes) -> None:
        s = tamper(seg) if tamper else seg
        if s is not None:
            b.on_segment(s)

    def b_to_a(seg: bytes) -> None:
        s = tamper(seg) if tamper else seg
        if s is not None:
            a.on_segment(s)
    a, b = SegmentedLink(a_to_b, mtu), SegmentedLink(b_to_a, mtu)
    return a, b


class BlessGattServer:  # pragma: no cover - needs a BLE radio (pod hardware)
    """Pod-side GATT peripheral using `bless` (MIT). Untested without hardware."""

    def __init__(self, name: str = "O Iris pod", mtu: int = DEFAULT_MTU):
        self.name, self.mtu = name, mtu
        self.link = SegmentedLink(self._notify, mtu)
        self._server = None

    def _notify(self, seg: bytes) -> None:
        if self._server is None:
            raise RuntimeError("GATT server not started")
        self._server.get_characteristic(TX_CHAR_UUID).value = bytearray(seg)
        self._server.update_value(SERVICE_UUID, TX_CHAR_UUID)

    async def start(self) -> None:
        from bless import BlessServer, GATTAttributePermissions, GATTCharacteristicProperties  # type: ignore[import-not-found]
        srv = BlessServer(name=self.name)
        srv.write_request_func = lambda _c, value, **_k: self.link.on_segment(bytes(value))
        await srv.add_new_service(SERVICE_UUID)
        await srv.add_new_characteristic(SERVICE_UUID, RX_CHAR_UUID,
                                         GATTCharacteristicProperties.write_without_response, None,
                                         GATTAttributePermissions.writeable)
        await srv.add_new_characteristic(SERVICE_UUID, TX_CHAR_UUID, GATTCharacteristicProperties.notify, None,
                                         GATTAttributePermissions.readable)
        await srv.start()
        self._server = srv

    async def stop(self) -> None:
        if self._server is not None:
            await self._server.stop()
            self._server = None
