# Live2D implementation and limits

The shipped `.moc3` is not an unrigged image. Runtime inspection finds 129 parameters and 47 physics settings with 115 inputs and 91 outputs. Standard head angle, gaze, eyelid, brow, mouth, and breath drivers are all present, and those drivers already propagate into the body, hair, skirt, apron, bows, sleeves, arms, back hair, ahoge, earrings, and hair accessories through `physics3.json`.

Nikki OS therefore uses the existing rig: a validated semantic state selects a bounded parameter motion, Cubism Core applies the compiled parameter-to-vertex mappings, and the physics configuration adds secondary motion. The parameter debugger exposes the discovered IDs and can export a snapshot. `scripts/audit_live2d_model.py` reproduces the audit in `qa/live2d-rig-audit.json`.

Source-level re-rigging is a different operation. Live2D documents `.cmo3` as the editable modeling workspace and `.moc3` as the exported application model. This repository contains no `.cmo3`, `.cmp3`, `.can3`, layered `.psd/.psb`, or `.cdi3.json`. Cubism Core exposes runtime parameters, parts, drawables, UVs, opacity, and calculated vertices; it does not reconstruct the Editor's deformer hierarchy, source layers, keyform authoring data, or editable mesh workspace. A faithful `.moc3 -> .cmo3` recovery is therefore not available.

If the original `.cmo3` is supplied later, keep the current parameter IDs, edit the model in Cubism Editor, export a replacement `.moc3`, and rerun the rig audit plus Windows smoke test. Layered art is additionally needed if parts must be split or repainted. Until then, runtime parameter drive is the non-destructive complete implementation possible from the supplied model; the sprite renderer remains the production fallback where the compiled motion range is insufficient.

Official format and runtime references:

- <https://docs.live2d.com/en/cubism-editor-manual/file-type-and-extension/>
- <https://docs.live2d.com/en/cubism-editor-manual/export-moc3-motion3-files/>
- <https://docs.live2d.com/en/cubism-sdk-manual/model/>
- <https://docs.live2d.com/en/cubism-sdk-manual/cubism-core-api-reference/>
