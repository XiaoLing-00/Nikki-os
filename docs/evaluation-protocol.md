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

## Automated engineering run

Run both renderers sequentially on the same machine with the fixed idle, talking, dragging, and roaming script:

```bash
python scripts/benchmark_renderers.py --duration-seconds 900 --output qa/renderer-benchmark.json
```

The report includes cold-start time, aggregate CPU and RSS for the complete process tree, native frame-pacing samples, late-frame ratio, and exercised states. The technical recommendation may select the production default, but it does not invent the five independent human visual ratings. Record those ratings separately if the project needs a formal user-study result; until then both renderers remain selectable.

## 2026-08-13 engineering result

Both renderers completed the fixed script for 900 seconds each on both operating systems:

| Platform | Renderer | Mean CPU | Mean process-tree RSS | Late-frame ratio | Cold start |
| --- | --- | ---: | ---: | ---: | ---: |
| macOS arm64 | Sprite | 1.594% | 91.151 MiB | 0.003636 | 0.491 s |
| macOS arm64 | Live2D | 41.479% | 333.174 MiB | 0.000241 | 0.759 s |
| Windows 11 | Sprite | 0.689% | 63.788 MiB | 0 | 0.100 s |
| Windows 11 | Live2D | 62.116% | 897.610 MiB | 0.013118 | 0.563 s |

The engineering default is therefore Sprite on both machines. Live2D remains selectable for users who prefer continuous 60 fps motion and accept its resource cost. The reports are `qa/renderer-benchmark-macos.json` and `qa/renderer-benchmark-windows.json`; the five-viewer preference panel remains uncollected.
