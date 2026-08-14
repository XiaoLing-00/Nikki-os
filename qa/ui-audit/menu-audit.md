# Context menu audit

- Surface: Nikki OS character right-click menu on macOS.
- User goal: find settings and companion actions without leaving the visual language of the desktop pet.
- Evidence: original native menu embedded in `qa/ui-audit/12-menu-before-after.png`.

## Step 1 - Open the character menu

Health: poor.

- The native gray menu is visually disconnected from the warm white, rose, rounded companion UI.
- Large system text and row heights make secondary/debug actions dominate the surface.
- `测试表情` is placed first even though it is a developer action; settings and memory are more useful to ordinary users.
- The solid disclosure arrow is heavier than the rest of the product icon language.
- Only the exit divider creates grouping, so utility, personal, and debug actions read as one undifferentiated list.
- Screenshot evidence cannot confirm keyboard focus, screen-reader labels, or contrast values; those require implementation checks.

## Recommended hierarchy

1. Primary: settings, memory.
2. Companion controls: screen analysis, feedback preferences.
3. Developer tools: expression testing and Live2D parameter debugging.
4. Destructive/terminal: exit, separated and rose-red only on hover.

## Visual direction

- Warm translucent white surface, 16 px radius, subtle rose border and shadow.
- 14 px system CJK typography and 36 px rows.
- Licensed outline icons matching the new hover launcher.
- Rose hover fill with dark plum text; no default gray system chrome.

## Post-implementation verification

### Step 1 - Open the character menu

Health: good.

- Replaced the native menu with a 282 px custom popup in the companion palette.
- Settings and memory are now first; debug actions are on the in-place more-tools page.
- The popup supports Escape, accessible button names, outside-click close, and screen-edge clamping.
- Main-page and tools-page renders passed visual inspection; 58 automated tests passed.
