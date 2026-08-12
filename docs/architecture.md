# Dual-renderer architecture

The agent layer produces only the validated `emotion` and `action` contract. `ActionMapper` converts it into a renderer-neutral `AnimationState`; `AnimationStateMachine` resolves priority and duration; the selected renderer consumes the same state.

```text
Observer / Persona / User input
              |
      validated JSON contract
              |
         ActionMapper
              |
    AnimationStateMachine
          /           \
 SpriteRenderer   Live2DRenderer
 PNG/WebP strips  Cubism parameters/motions
```

This separation prevents model output from naming files, JavaScript functions, or Cubism parameters directly. Unknown values are normalized before they reach either renderer.

The Live2D side is parameter-driven rather than file-driven: an AI reply can select only a safe semantic action, `Live2DRenderer` maps that state to a bounded motion profile, and the profile drives existing Cubism parameters. Cubism Core then evaluates the parameter-to-ArtMesh/deformer mappings and `physics3.json` chains. The model never receives permission to address arbitrary parameter IDs or JavaScript functions.
