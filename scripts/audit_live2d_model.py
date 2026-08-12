from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from renderers.live2d_renderer import Live2DRenderer  # noqa: E402

STANDARD_DRIVERS = (
    "ParamAngleX",
    "ParamAngleY",
    "ParamAngleZ",
    "ParamEyeBallX",
    "ParamEyeBallY",
    "ParamEyeLOpen",
    "ParamEyeROpen",
    "ParamBrowLY",
    "ParamBrowLY2",
    "ParamMouthOpenY",
    "ParamMouthForm",
    "ParamBreath",
)


def build_report(parameters: list[dict], model_path: Path) -> dict:
    model = json.loads(model_path.read_text(encoding="utf-8"))
    physics_path = model_path.parent / model["FileReferences"]["Physics"]
    physics = json.loads(physics_path.read_text(encoding="utf-8"))
    editable_patterns = ("*.cmo3", "*.can3", "*.cmp3", "*.psd", "*.psb")
    editable_sources = sorted(
        str(path.relative_to(ROOT))
        for pattern in editable_patterns
        for path in ROOT.glob(f"**/{pattern}")
    )
    parameter_ids = {str(item.get("id")) for item in parameters}
    physics_names = {
        item["Id"]: item.get("Name", item["Id"])
        for item in physics.get("Meta", {}).get("PhysicsDictionary", [])
    }
    physics_links = []
    for setting in physics.get("PhysicsSettings", []):
        physics_links.append(
            {
                "id": setting.get("Id"),
                "name": physics_names.get(setting.get("Id"), setting.get("Id")),
                "inputs": sorted({item["Source"]["Id"] for item in setting.get("Input", [])}),
                "outputs": sorted(
                    {item["Destination"]["Id"] for item in setting.get("Output", [])}
                ),
            }
        )

    editable_model_sources = [
        path for path in editable_sources if path.lower().endswith((".cmo3", ".cmp3"))
    ]
    layered_art_sources = [
        path for path in editable_sources if path.lower().endswith((".psd", ".psb"))
    ]
    source_level_possible = bool(editable_model_sources)
    standard_support = {name: name in parameter_ids for name in STANDARD_DRIVERS}
    return {
        "schema_version": 1,
        "model": str(model_path.relative_to(ROOT)),
        "compiled_model": str((model_path.parent / model["FileReferences"]["Moc"]).relative_to(ROOT)),
        "parameter_count": len(parameters),
        "parameters": parameters,
        "standard_driver_support": standard_support,
        "physics": {
            "setting_count": len(physics_links),
            "input_count": physics.get("Meta", {}).get("TotalInputCount"),
            "output_count": physics.get("Meta", {}).get("TotalOutputCount"),
            "links": physics_links,
        },
        "editable_sources": editable_sources,
        "editable_model_sources": editable_model_sources,
        "layered_art_sources": layered_art_sources,
        "source_level_rerig_possible": source_level_possible,
        "runtime_parameter_drive_possible": all(standard_support.values()),
        "already_rigged": len(parameters) > 0 and len(physics_links) > 0,
        "decision": (
            "edit-and-reexport-cmo3" if source_level_possible else "drive-existing-moc3-parameters"
        ),
        "reason": (
            "Editable model and layered art were found."
            if source_level_possible
            else "Only compiled runtime model data is present; preserve its existing parameter-to-vertex rig."
        ),
        "official_references": [
            "https://docs.live2d.com/en/cubism-editor-manual/file-type-and-extension/",
            "https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/",
            "https://docs.live2d.com/en/cubism-sdk-manual/model/",
            "https://docs.live2d.com/en/cubism-sdk-manual/cubism-core-api-reference/",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the shipped Live2D rig through Cubism Core.")
    parser.add_argument("--output", type=Path, default=ROOT / "qa" / "live2d-rig-audit.json")
    parser.add_argument("--timeout-seconds", type=int, default=30)
    args = parser.parse_args()

    app = QApplication(["nikki-live2d-audit"])
    model_path = ROOT / "assets" / "live2d" / "nikki" / "model3.json"
    viewer_path = ROOT / "assets" / "live2d" / "viewer.html"
    renderer = Live2DRenderer(viewer_path, model_path)
    renderer.resize(430, 660)
    renderer.show()
    state = {"finished": False, "exit_code": 2}

    def finish(parameters) -> None:
        if state["finished"] or not parameters:
            return
        state["finished"] = True
        report = build_report(parameters, model_path)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "output": str(args.output),
                    "parameter_count": report["parameter_count"],
                    "physics_setting_count": report["physics"]["setting_count"],
                    "source_level_rerig_possible": report["source_level_rerig_possible"],
                    "decision": report["decision"],
                },
                ensure_ascii=False,
            )
        )
        state["exit_code"] = 0
        app.quit()

    def on_log(message: str) -> None:
        if "Live2D model loaded" in message and not state["finished"]:
            renderer.get_parameters(finish)

    def timeout() -> None:
        if not state["finished"]:
            print("Live2D audit timed out before parameter discovery.", file=sys.stderr)
            app.quit()

    renderer.bridge.log.connect(on_log)
    QTimer.singleShot(args.timeout_seconds * 1000, timeout)
    app.exec()
    return int(state["exit_code"])


if __name__ == "__main__":
    raise SystemExit(main())
