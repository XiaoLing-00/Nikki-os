# Renderer evaluation protocol

Compare sprite and Live2D builds with the same machine, prompts, character window size, and 15-minute script. Do not compare different model replies.

Record for each renderer:

1. Cold start time until the character is visible.
2. Idle CPU and RSS after five minutes.
3. Frame pacing while idle, talking, dragging, and roaming.
4. Correct-state rate for the fixed actions: greeting, listening, thinking, talking, comfort, happy, angry, dragging, sleeping.
5. Visual ratings from at least five viewers: identity consistency, motion naturalness, emotional clarity, edge quality, and overall preference (1-5).
6. Functional failures, blank frames, missing assets, and offline startup result.

Choose the final renderer only after both modes pass functional checks. Suggested decision score: stability 35%, visual preference 30%, semantic clarity 20%, resource cost 15%.
