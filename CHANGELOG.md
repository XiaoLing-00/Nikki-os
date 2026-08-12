# Changelog

## 0.2.0

- Added selectable sprite and Live2D renderers behind one semantic animation state machine.
- Added validated sprite resources and generated talking, listening, comfort, dragging, angry, happy, sleeping, and error strips.
- Made Live2D runtime fully offline and added parameter inspection/control.
- Audited the compiled Live2D rig through Cubism Core (129 parameters and 47 physics chains), fixed parameter debugger serialization, and added semantic error/sleep/roam parameter motions.
- Added repeatable same-machine renderer performance benchmarking with process-tree CPU/RSS and frame-pacing evidence.
- Removed residual green matte from the complete sprite atlas and custom strips, with raw, 2x bilinear, dark-background, light-background, macOS, and Windows deterministic Qt runtime checks.
- Enforced a versioned model JSON contract with schema validation and bounded retries.
- Added privacy controls, memory management, sensitive-data rejection, tray controls, and cross-platform autostart adapters.
- Added `--doctor`, macOS/Windows tests, Windows PyInstaller packaging, and reproducible visual QA artifacts.
