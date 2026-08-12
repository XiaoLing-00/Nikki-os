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
