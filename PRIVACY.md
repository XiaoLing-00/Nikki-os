# Privacy

Nikki OS defaults to the minimum desktop context: application category only. Window titles, screenshots, microphone input, and cloud model calls are independently controlled.

- Screenshot analysis is off by default. A screenshot is written to an OS temporary file, uploaded only after an explicit user action, and deleted in `finally`.
- Window-title reading can be set to `off`, `app_only`, or `window_title`. Password managers, banking, and payment applications are excluded before context is created.
- Long-term memory is local SQLite. API keys, passwords, tokens, phone numbers, identity-card numbers, and email addresses are rejected. Users can inspect, edit, delete, or clear memories.
- Microphone capture starts only after an explicit button/key action, has a time limit, and deletes its temporary WAV after recognition.
- API keys belong in `.env`, which is ignored by Git. They are never included in logs, preferences, screenshots, builds, or test fixtures.

The DashScope text, vision, and speech features transmit the requested content to Alibaba Cloud under that service's terms. Sprite rendering, Live2D rendering, settings, and local memory do not require network access.
