**Comparison target**

- Source visual truth: selected Option 3 concept embedded in `qa/ui-audit/06-option3-refined-side-by-side.png`.
- Implementation screenshot: `qa/ui-audit/07-option3-final-hover.png`
- Full comparison: `qa/ui-audit/06-option3-refined-side-by-side.png`
- Viewport and CSS size: 430 x 660 px, device scale factor 1
- Source pixels: 1012 x 1554, normalized to 430 x 660 for comparison
- Implementation pixels: 430 x 660
- State: character hover, compact chat launcher visible, full chat closed

**Findings**

- No actionable P0, P1, or P2 findings remain.
- Typography uses the intended system CJK family stack, regular 14 px text, and matches the selected compact hierarchy.
- Spacing and layout match the selected 184 x 48 px capsule, with the character unobstructed.
- Colors use the selected warm white, plum text, and rose action token with a restrained shadow.
- The existing production character asset is intentionally preserved instead of the slightly regenerated character shown in the concept image. This keeps asset quality and animation consistency intact.
- The icon is a licensed Material Design outline conversation icon from QtAwesome rather than a handcrafted approximation.
- Copy matches the selected direction: `和暖暖说话`.

**Focused evidence**

- A separate crop was not needed because the 184 x 48 px launcher is clearly readable at 1:1 in the full implementation screenshot.
- Interaction checks passed for hover reveal, launcher click to open chat, and Escape to close chat.

**Comparison history**

1. First implementation (`02-option3-hover-implementation.png`): capsule was too wide and high, text was too heavy, and the icon was filled.
2. Refinement (`05-option3-hover-refined.png`): capsule changed from 192 px to 184 px, moved down 10 px, text weight changed to regular, and an outline icon was used.
3. Final (`07-option3-final-hover.png`): outline icon changed to the closer conversation-bubble-with-dots form; interaction and regression tests passed.

**Follow-up polish**

- P3: Windows font rendering and native transparency should be visually checked again during the required native Windows packaging acceptance pass.

## Context menu redesign

- Source screenshot: original native menu embedded in `qa/ui-audit/12-menu-before-after.png`.
- Implementation screenshot: `qa/ui-audit/10-custom-menu-final.png`
- More-tools screenshot: `qa/ui-audit/11-custom-menu-tools-final.png`
- Before/after comparison: `qa/ui-audit/12-menu-before-after.png`
- Implementation: `ui/companion_menu.py`
- Source pixels and component size: 430 x 320 px at device scale factor 1.
- Implementation pixels and component size: 282 x 321 px at device scale factor 1; the reduced width is the intended density change.
- Full comparison canvas: 780 x 390 px with both components shown at 1:1 density.
- State: character context menu open; main and more-tools pages checked.

### Findings

- No actionable P0, P1, or P2 findings remain.
- The native 430 px-wide gray menu is replaced by a 282 px-wide custom popup using the existing warm white, plum, and rose tokens.
- Settings and memory lead the hierarchy; screen analysis and reminder feedback form the companion-control group.
- Expression and Live2D debug actions move to an in-place more-tools page, so developer controls no longer dominate the default surface.
- Feedback actions share one compact row and the terminal exit action remains separate.
- All icons are licensed Font Awesome icons delivered through QtAwesome.
- Keyboard Escape closes the popup; buttons expose accessible names; screen-edge positioning is clamped to the available display area.
- A focused crop was not needed because all menu labels, icons, separators, radii, and the shadow are legible at 1:1 in the full comparison.

### Comparison history

1. Native menu: system chrome, oversized text and rows, no meaningful grouping, developer action first.
2. First custom render (`08-custom-menu-main.png`): hierarchy and palette were correct, but the exit button inherited native push-button chrome.
3. Final render (`10-custom-menu-final.png`): exit styling now matches the other menu rows while retaining a restrained rose danger color.

### Validation

- Main and more-tools render inspection passed at device scale factor 1.
- Focused menu interactions passed for page switching, callback dispatch, and popup close.
- Full suite: 58 passed.
- Ruff and `git diff --check`: passed.
- P3: repeat the visual check on native Windows during the Windows packaging acceptance pass.

final result: passed
