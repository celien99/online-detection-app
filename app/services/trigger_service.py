"""Triggered production inspection orchestration."""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Callable

from app.infrastructure.camera.manager import CameraManager
from app.infrastructure.line_signal import (
    CaptureRequest,
    InspectionDecision,
    InspectionResultSignal,
    LineSignalAdapter,
    VirtualLineSignalAdapter,
)
from app.infrastructure.plc.interface import LineStatus
from app.services.inspection_service import InspectionService


@dataclass(slots=True)
class TriggerState:
    mode: str = "continuous"
    connected: bool = False
    line_status: str = "unknown"
    waiting: bool = True
    busy: bool = False
    last_request_id: str = ""
    last_part_id: str = ""
    last_result: str = ""
    last_error: str = ""
    last_trigger_at: float = 0.0
    last_completed_at: float = 0.0


class TriggerService:
    """Consumes line capture requests and runs one inspection per trigger."""

    def __init__(
        self,
        *,
        adapter: LineSignalAdapter,
        camera_manager: CameraManager,
        inspection_service: InspectionService,
        handle_response: Callable[[Any, dict], None],
        mode: str = "triggered",
        poll_interval_s: float = 0.05,
        capture_timeout_s: float = 2.0,
    ) -> None:
        self._adapter = adapter
        self._camera_manager = camera_manager
        self._inspection = inspection_service
        self._handle_response = handle_response
        self._mode = mode
        self._poll_interval_s = poll_interval_s
        self._capture_timeout_s = capture_timeout_s
        self._running = False
        self._thread: threading.Thread | None = None
        self._state = TriggerState(mode=mode)
        self._state_lock = threading.Lock()
        self._manual_adapter = adapter if isinstance(adapter, VirtualLineSignalAdapter) else None
        self._manual_requests: list[CaptureRequest] = []
        self._manual_lock = threading.Lock()

    @property
    def adapter(self) -> LineSignalAdapter:
        return self._adapter

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="trigger-service")
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)

    def manual_trigger(self, *, part_id: str = "", seat_model_id: str | None = None) -> bool:
        if self._manual_adapter is None:
            with self._manual_lock:
                self._manual_requests.append(
                    CaptureRequest(
                        request_id=f"manual-{int(time.time() * 1000)}",
                        part_id=part_id,
                        seat_model_id=seat_model_id,
                        source="manual",
                    )
                )
            return True
        self._manual_adapter.queue_capture_request(
            part_id=part_id,
            seat_model_id=seat_model_id,
            source="manual",
        )
        return True

    def get_state(self) -> TriggerState:
        with self._state_lock:
            return TriggerState(
                mode=self._state.mode,
                connected=self._state.connected,
                line_status=self._state.line_status,
                waiting=self._state.waiting,
                busy=self._state.busy,
                last_request_id=self._state.last_request_id,
                last_part_id=self._state.last_part_id,
                last_result=self._state.last_result,
                last_error=self._state.last_error,
                last_trigger_at=self._state.last_trigger_at,
                last_completed_at=self._state.last_completed_at,
            )

    def _loop(self) -> None:
        while self._running:
            try:
                self._update_line_state()
                request = self._pop_manual_request() or self._adapter.poll_capture_request()
                if request is None:
                    time.sleep(self._poll_interval_s)
                    continue
                self._run_request(request)
            except Exception as exc:
                self._adapter.send_fault(None, "trigger_loop_failed", str(exc))
                self._set_state(last_error=str(exc), busy=False, waiting=True)
                time.sleep(0.2)

    def _run_request(self, request: CaptureRequest) -> None:
        self._set_state(
            busy=True,
            waiting=False,
            last_request_id=request.request_id,
            last_part_id=request.part_id,
            last_error="",
            last_trigger_at=time.time(),
        )
        self._adapter.send_busy(request, True)
        try:
            frames = self._capture_frames_until_timeout()
            if not frames:
                raise RuntimeError("capture_timeout_no_frames")
            response = self._inspection.inspect_sync(
                frames,
                seat_model_id=request.seat_model_id,
                timeout_s=5.0,
            )
            self._handle_response(response, frames)
            result_signal = _build_result_signal(request, response)
            self._adapter.send_result(result_signal)
            self._set_state(
                last_result=result_signal.status.value,
                last_completed_at=time.time(),
            )
        except Exception as exc:
            self._adapter.send_fault(request, "inspection_failed", str(exc))
            self._set_state(last_error=str(exc), last_result="FAULT")
            raise
        finally:
            self._adapter.send_busy(request, False)
            self._set_state(busy=False, waiting=True)

    def _capture_frames_until_timeout(self) -> dict:
        deadline = time.time() + self._capture_timeout_s
        last_frames: dict = {}
        while time.time() <= deadline:
            frames = self._camera_manager.grab_all()
            valid_frames = {cid: frame for cid, frame in frames.items() if frame is not None}
            if valid_frames:
                return valid_frames
            last_frames = frames
            time.sleep(0.01)
        return {cid: frame for cid, frame in last_frames.items() if frame is not None}

    def _pop_manual_request(self) -> CaptureRequest | None:
        with self._manual_lock:
            if not self._manual_requests:
                return None
            return self._manual_requests.pop(0)

    def _update_line_state(self) -> None:
        try:
            line_status = self._adapter.read_line_status()
        except Exception:
            line_status = LineStatus.UNKNOWN
        self._set_state(
            connected=self._adapter.connected,
            line_status=line_status.value,
        )

    def _set_state(self, **updates: Any) -> None:
        with self._state_lock:
            for key, value in updates.items():
                setattr(self._state, key, value)


def _build_result_signal(request: CaptureRequest, response: Any) -> InspectionResultSignal:
    status = str(getattr(response, "status", "REJECT") or "REJECT")
    decision = {
        "OK": InspectionDecision.OK,
        "NG": InspectionDecision.NG,
        "REJECT": InspectionDecision.REJECT,
    }.get(status, InspectionDecision.REJECT)
    defect_type = ""
    confidence = 0.0
    reason = str(getattr(response, "decision_reason", "") or "")

    if hasattr(response, "result") and hasattr(response.result, "camera_results"):
        for cr in response.result.camera_results:
            if not reason:
                reason = str(getattr(cr, "reason", "") or "")
            if getattr(cr, "status", "") == "NG":
                if hasattr(cr, "filter_result") and cr.filter_result:
                    defect_type = str(getattr(cr.filter_result, "class_name", "") or "")
                if hasattr(cr, "texture_result") and cr.texture_result:
                    confidence = float(getattr(cr.texture_result, "score", 0.0) or 0.0)
                break

    return InspectionResultSignal(
        request_id=request.request_id,
        status=decision,
        part_id=request.part_id,
        defect_code=_defect_type_to_code(defect_type),
        defect_type=defect_type,
        confidence=confidence,
        reason=reason,
    )


def _defect_type_to_code(defect_type: str) -> int:
    if not defect_type:
        return 0
    return abs(hash(defect_type)) % 32767 or 1
