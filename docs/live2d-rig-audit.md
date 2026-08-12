# Live2D rig decision

## Result

The supplied Nikki model is already richly rigged. A real Cubism Core load reports:

- 129 runtime parameters;
- 47 physics settings;
- 115 physics inputs and 91 physics outputs;
- working head X/Y/Z, eye X/Y, eyelid, brow, mouth, and breath drivers;
- secondary chains for the body, waist/legs, eyes, hair sections, skirt, apron, bows, sleeve lace, arms, back hair, ahoge, earrings, and hair accessories.

The selected implementation is **drive the existing compiled rig**, not reconstruct a new one from textures. Safe semantic states map to bounded parameter profiles in `viewer.html`; the model response cannot name arbitrary Cubism parameters.

## Why source re-rigging is not claimed

Live2D's file documentation distinguishes editable `.cmo3` modeling data from exported `.moc3` application data. The repository has only the exported model, textures, physics, expressions, and one idle motion. It has no editable `.cmo3/.cmp3`, animation `.can3`, layered `.psd/.psb`, or parameter-name `.cdi3.json` source. An editable `.cmo3` would be sufficient to refine its existing deformers; layered artwork is additionally needed when parts must be split or repainted.

Cubism Core can calculate and expose runtime parameter, part, drawable, mesh, UV, opacity, and vertex state. That is sufficient for playback, inspection, motion synthesis, and parameter driving, but not for recreating the Editor's authoring hierarchy and source artwork. Creating a fresh model from the flattened texture atlas would be a new manual rig, not recovery of the original model, and would likely reduce fidelity.

## Reproduce the audit

```bash
python scripts/audit_live2d_model.py --output qa/live2d-rig-audit.json
```

The command fails if the model does not load or no parameters are returned. Its JSON output records every discovered parameter and every physics input/output link.

## If editable source becomes available

1. Back up the original `.cmo3`, `.can3`, and layered art.
2. Preserve the standard parameter IDs already consumed by Nikki OS.
3. Add or refine deformers and keyforms in Cubism Editor.
4. Export a replacement `.moc3`, textures, physics, motions, and `.cdi3.json`.
5. Rerun the audit, parameter debugger, macOS smoke, Windows smoke, and renderer benchmark.

Official references:

- <https://docs.live2d.com/en/cubism-editor-manual/file-type-and-extension/>
- <https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/>
- <https://docs.live2d.com/en/cubism-sdk-manual/model/>
- <https://docs.live2d.com/en/cubism-sdk-manual/cubism-core-api-reference/>
