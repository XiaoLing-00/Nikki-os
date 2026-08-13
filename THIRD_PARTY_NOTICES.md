# Third-party notices

Nikki OS uses [`edge-tts`](https://github.com/rany2/edge-tts) to access the
Microsoft Edge online text-to-speech service without an API key. `edge-tts`
7.2.8 is licensed under LGPL-3.0, except for its `srt_composer.py` component,
which is MIT licensed. Its source code and full license text are available in
the linked upstream repository and in the installed Python package.

The online service is network-dependent and has no availability guarantee from
this project. Nikki OS automatically falls back to the operating system's local
text-to-speech engine when online synthesis is unavailable.

Nikki OS uses [`QtAwesome`](https://github.com/spyder-ide/qtawesome) for its
cross-platform interface icons. QtAwesome is MIT licensed. Its bundled icon
fonts retain their upstream licenses; the complete notices and license files
are distributed inside the installed `qtawesome` package.
