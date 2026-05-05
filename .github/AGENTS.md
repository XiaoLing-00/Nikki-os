# NIKKI-os Agent Instructions

Use this repository as a Python 3.10+ desktop companion app with a four-layer architecture: Perception, Cognition, Memory, and Action/UI. Keep changes aligned with that split and prefer small edits within the owning layer.

## What to read first

- [README.md](../README.md) for the project architecture and JSON protocol.
- [services/llm_service.py](../services/llm_service.py) for model-facing behavior.
- [perception/context_builder.py](../perception/context_builder.py) for perception-to-context flow.
- [memory/short_memory.py](../memory/short_memory.py) and [memory/long_memory.py](../memory/long_memory.py) for memory behavior.
- [ui/live2d_widget.py](../ui/live2d_widget.py) and [ui/main_window.py](../ui/main_window.py) for rendering and interaction.

## Working rules

- Preserve the standard JSON contract between agents and the UI: `context`, `response`, and `memory_update`.
- Treat `response.emotion` and `response.action` as identifiers consumed by the Live2D layer; do not rename or invent values without updating the mapping logic.
- Keep perception, memory, and UI concerns separated. Avoid moving decision logic into the UI or rendering code.
- Prefer linking to the README and source files instead of restating architecture details here.
- Make the smallest change that fixes the issue and avoid broad refactors unless the task explicitly asks for them.

## Known conventions and pitfalls

- The project currently depends on PyQt6 and PyQt6-WebEngine; there is no separate build system or test harness documented yet.
- `main.py` is currently empty, so the real entry points are the layer modules under `agents/`, `services/`, `memory/`, `perception/`, and `ui/`.
- Live2D assets live under [assets/live2d/nikki/](../assets/live2d/nikki/); keep expression and motion file names consistent with the code that selects them.
- If you need to change runtime behavior, check whether the decision belongs in the observer agent, persona agent, or UI controller before editing.

## Validation

- For Python edits, use the narrowest useful check available for the touched files.
- If no targeted test exists, prefer a syntax or import check over a broad project-wide run.
- Do not add new dependencies unless the task clearly requires them.