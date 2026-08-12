# Live2D implementation and limits

The shipped `.moc3` is a compiled Cubism model. Nikki OS can safely drive its existing parameters, expressions, drawable visibility, gaze vector, and simulated motions at runtime. The parameter debugger exposes discovered parameter IDs and can export a snapshot.

True bone/deformer re-rigging requires the editable Cubism Editor source (`.cmo3` or `.can3`) plus the layered source art. Those files are not present, so this project does not claim to have rebound the skeleton. Runtime parameter control is the complete implementation possible from the supplied binary model; the sprite renderer is the production fallback when its motion range is insufficient.
