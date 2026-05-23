# NIKKI-os Agent Instructions

Use this repository as a Python 3.10+ desktop companion app with a four-layer architecture: Perception, Cognition, Memory, and Action/UI. Keep changes aligned with that split and prefer small edits within the owning layer.

## What to read first

- [README.md](../README.md) for the project architecture and JSON protocol.
- [services/llm_service.py](../services/llm_service.py) for model-facing behavior.
- [perception/context_builder.py](../perception/context_builder.py) for perception-to-context flow.
- [memory/short_memory.py](../memory/short_memory.py) and [memory/long_memory.py](../memory/long_memory.py) for memory behavior.
- [ui/sprite_pet_widget.py](../ui/sprite_pet_widget.py), [ui/action_controller.py](../ui/action_controller.py), [ui/speech_bubble.py](../ui/speech_bubble.py), and [ui/main_window.py](../ui/main_window.py) for rendering and interaction.

## Working rules

- Preserve the standard JSON contract between agents and the UI: `context`, `response`, and `memory_update`.
- Treat `response.emotion` and `response.action` as semantic identifiers consumed by `ActionController`; do not rename or invent values without updating the mapping logic and tests.
- Keep perception, memory, and UI concerns separated. Avoid moving decision logic into the UI or rendering code.
- Prefer linking to the README and source files instead of restating architecture details here.
- Make the smallest change that fixes the issue and avoid broad refactors unless the task explicitly asks for them.

## Known conventions and pitfalls

- The project currently depends on PyQt6; use `main.py` as the desktop app entry point.
- Codex pet assets live under [assets/pets/nuannuan/](../assets/pets/nuannuan/); keep `pet.json`, `spritesheet.webp`, and `actions/actions.json` consistent with `SpritePetWidget`.
- If you need to change runtime behavior, check whether the decision belongs in the observer agent, persona agent, or UI controller before editing.

## Validation

- For Python edits, use the narrowest useful check available for the touched files.
- If no targeted test exists, prefer a syntax or import check over a broad project-wide run.
- Do not add new dependencies unless the task clearly requires them.
