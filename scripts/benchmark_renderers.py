from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path
from time import perf_counter

import psutil
from PyQt6.QtCore import QEvent, QObject, QTimer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from animation.states import AnimationState  # noqa: E402
from config.settings import Settings  # noqa: E402
from renderers.factory import create_renderer  # noqa: E402

STATE_SCRIPT = (
    (AnimationState.IDLE, "wink", "motion_idle"),
    (AnimationState.TALKING, "wink", "motion_talk"),
    (AnimationState.DRAGGING, "awkward", "motion_dragging"),
    (AnimationState.ROAM_RIGHT, "wink", "motion_idle"),
)


def percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, int(len(ordered) * quantile + 0.999999) - 1))
    return round(ordered[index], 3)


def summarize(values: list[float]) -> dict:
    if not values:
        return {"samples": 0, "mean": None, "median": None, "p95": None, "maximum": None}
    return {
        "samples": len(values),
        "mean": round(statistics.fmean(values), 3),
        "median": round(statistics.median(values), 3),
        "p95": percentile(values, 0.95),
        "maximum": round(max(values), 3),
    }


class PaintProbe(QObject):
    def __init__(self, callback) -> None:
        super().__init__()
        self.callback = callback
        self.seen = False

    def eventFilter(self, watched, event) -> bool:
        if not self.seen and event.type() == QEvent.Type.Paint:
            self.seen = True
            self.callback()
        return super().eventFilter(watched, event)


class ResourceSampler:
    def __init__(self) -> None:
        self.root = psutil.Process()
        self.processes: dict[int, psutil.Process] = {}
        self.cpu_percent: list[float] = []
        self.rss_mib: list[float] = []
        self.sample(initialize=True)

    def sample(self, initialize: bool = False) -> None:
        try:
            candidates = [self.root, *self.root.children(recursive=True)]
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            candidates = [self.root]
        live_pids = set()
        total_cpu = 0.0
        total_rss = 0
        for candidate in candidates:
            try:
                pid = candidate.pid
                live_pids.add(pid)
                process = self.processes.get(pid)
                if process is None:
                    process = candidate
                    self.processes[pid] = process
                    process.cpu_percent(None)
                elif not initialize:
                    total_cpu += process.cpu_percent(None)
                total_rss += process.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        self.processes = {pid: process for pid, process in self.processes.items() if pid in live_pids}
        if not initialize:
            self.cpu_percent.append(total_cpu)
            self.rss_mib.append(total_rss / (1024 * 1024))


def worker(renderer_name: str, duration_seconds: int, output: Path) -> int:
    os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu-sandbox")
    app = QApplication([f"nikki-{renderer_name}-benchmark"])
    started = perf_counter()
    renderer = create_renderer(Settings(renderer_backend=renderer_name))
    renderer.resize(430, 660)
    state = {
        "ready": False,
        "finished": False,
        "ready_seconds": None,
        "state_index": 0,
        "frame_previous": None,
        "frame_intervals": [],
        "expected_intervals": [],
    }
    sampler = ResourceSampler()
    sample_timer = QTimer()
    sample_timer.timeout.connect(sampler.sample)
    state_timer = QTimer()

    def play_state(index: int) -> None:
        semantic, emotion, action = STATE_SCRIPT[index]
        renderer.play_state(semantic, emotion, action)
        state["state_index"] = index
        state["frame_previous"] = None

    def next_state() -> None:
        next_index = min(int(state["state_index"]) + 1, len(STATE_SCRIPT) - 1)
        play_state(next_index)
        if next_index == len(STATE_SCRIPT) - 1:
            state_timer.stop()

    def record_sprite_frame() -> None:
        now = perf_counter()
        previous = state["frame_previous"]
        state["frame_previous"] = now
        if previous is None:
            return
        config = renderer._config()  # type: ignore[attr-defined]
        fps = max(1, int(config.get("fps", 8)))
        state["frame_intervals"].append((now - previous) * 1000)
        state["expected_intervals"].append(1000 / fps)

    if renderer_name == "sprite":
        renderer._timer.timeout.connect(record_sprite_frame)  # type: ignore[attr-defined]

    def write_report(live2d_stats: dict | None = None) -> None:
        if state["finished"]:
            return
        state["finished"] = True
        sample_timer.stop()
        state_timer.stop()
        sampler.sample()
        intervals = [float(value) for value in state["frame_intervals"]]
        expected = [float(value) for value in state["expected_intervals"]]
        if renderer_name == "sprite":
            late_count = sum(
                actual > target * 1.5 for actual, target in zip(intervals, expected, strict=True)
            )
            frame_stats = {
                "sample_count": len(intervals),
                "average_ms": round(statistics.fmean(intervals), 3) if intervals else None,
                "p95_ms": percentile(intervals, 0.95),
                "maximum_ms": round(max(intervals), 3) if intervals else None,
                "late_frame_ratio": round(late_count / len(intervals), 6) if intervals else None,
                "native_rate": "state-dependent 4-10 fps",
            }
        else:
            payload = live2d_stats or {}
            frame_stats = {
                "sample_count": int(payload.get("sampleCount", 0)),
                "average_ms": payload.get("averageMs"),
                "p95_ms": payload.get("p95Ms"),
                "maximum_ms": payload.get("maximumMs"),
                "late_frame_ratio": payload.get("lateFrameRatio"),
                "native_rate": "WebGL display ticker",
            }
        report = {
            "renderer": renderer_name,
            "platform": platform.platform(),
            "python": platform.python_version(),
            "duration_seconds": duration_seconds,
            "ready": bool(state["ready"]),
            "cold_start_seconds": state["ready_seconds"],
            "states_exercised": [item[0].value for item in STATE_SCRIPT],
            "resources": {
                "cpu_percent_process_tree": summarize(sampler.cpu_percent),
                "rss_mib_process_tree": summarize(sampler.rss_mib),
            },
            "frame_pacing": frame_stats,
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        app.quit()

    def finish() -> None:
        if renderer_name == "live2d" and hasattr(renderer, "get_frame_stats"):
            renderer.get_frame_stats(write_report)
            QTimer.singleShot(3000, lambda: write_report({}))
        else:
            write_report()

    def mark_ready() -> None:
        if state["ready"]:
            return
        state["ready"] = True
        state["ready_seconds"] = round(perf_counter() - started, 3)
        if hasattr(renderer, "reset_frame_stats"):
            renderer.reset_frame_stats()
        sampler.sample(initialize=True)
        sample_timer.start(1000)
        play_state(0)
        state_timer.start(max(1000, round(duration_seconds * 1000 / len(STATE_SCRIPT))))
        QTimer.singleShot(duration_seconds * 1000, finish)

    if renderer_name == "live2d":
        renderer.bridge.log.connect(  # type: ignore[attr-defined]
            lambda message: mark_ready() if "Live2D model loaded" in message else None
        )
    else:
        paint_probe = PaintProbe(mark_ready)
        renderer.installEventFilter(paint_probe)

    # Install readiness hooks before showing the window. Windows can dispatch
    # the first paint immediately, so showing earlier makes the sprite probe
    # miss the event and falsely reports a healthy renderer as not ready.
    renderer.show()
    if renderer_name == "sprite":
        # Some Windows Qt backends deliver the first paint to a native child
        # rather than the top-level widget. A successful grab is an explicit,
        # cross-platform proof that the renderer can produce a frame.
        def verify_sprite_frame() -> None:
            if state["ready"]:
                return
            if not renderer.grab().isNull():
                mark_ready()

        QTimer.singleShot(50, verify_sprite_frame)

    def readiness_timeout() -> None:
        if not state["ready"]:
            write_report()

    QTimer.singleShot(45000, readiness_timeout)
    app.exec()
    return 0 if state["ready"] else 2


def choose_default(results: dict[str, dict]) -> str:
    ready = [name for name, result in results.items() if result.get("ready")]
    if len(ready) == 1:
        return ready[0]
    if not ready:
        return "none"

    def cost(name: str) -> float:
        resources = results[name]["resources"]
        cpu = resources["cpu_percent_process_tree"].get("mean") or 0
        rss = resources["rss_mib_process_tree"].get("mean") or 0
        late = results[name]["frame_pacing"].get("late_frame_ratio") or 0
        return float(cpu) + float(rss) / 10 + float(late) * 100

    return min(ready, key=cost)


def orchestrate(duration_seconds: int, output: Path) -> int:
    results: dict[str, dict] = {}
    with tempfile.TemporaryDirectory(prefix="nikki_renderer_benchmark_") as temporary:
        temp = Path(temporary)
        for renderer_name in ("sprite", "live2d"):
            result_path = temp / f"{renderer_name}.json"
            command = [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                renderer_name,
                "--duration-seconds",
                str(duration_seconds),
                "--output",
                str(result_path),
            ]
            completed = subprocess.run(
                command,
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                timeout=duration_seconds + 120,
            )
            if not result_path.exists():
                raise RuntimeError(
                    f"{renderer_name} benchmark failed ({completed.returncode}): {completed.stderr[-1000:]}"
                )
            results[renderer_name] = json.loads(result_path.read_text(encoding="utf-8"))
            results[renderer_name]["worker_exit_code"] = completed.returncode

    recommendation = choose_default(results)
    report = {
        "schema_version": 1,
        "method": "sequential same-machine renderer benchmark",
        "duration_seconds_per_renderer": duration_seconds,
        "fixed_window_size": [430, 660],
        "fixed_state_script": [item[0].value for item in STATE_SCRIPT],
        "results": results,
        "engineering_default_recommendation": recommendation,
        "human_visual_panel": {
            "status": "not_collected",
            "required_viewers": 5,
            "reason": "Viewer preference requires independent human judgments and is not synthesized.",
        },
        "selection": (
            f"Use {recommendation} as the production default on this machine; keep the other renderer selectable."
            if recommendation != "none"
            else "No renderer reached ready state."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "recommendation": recommendation}, ensure_ascii=False))
    return 0 if recommendation != "none" else 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark sprite and Live2D renderers.")
    parser.add_argument("--worker", choices=("sprite", "live2d"))
    parser.add_argument("--duration-seconds", type=int, default=900)
    parser.add_argument("--output", type=Path, default=ROOT / "qa" / "renderer-benchmark.json")
    args = parser.parse_args()
    duration = max(4, args.duration_seconds)
    if args.worker:
        return worker(args.worker, duration, args.output)
    return orchestrate(duration, args.output)


if __name__ == "__main__":
    raise SystemExit(main())
