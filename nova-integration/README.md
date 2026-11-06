# Nova integration (optional)

These two files are **sections for Nova (Jarvis.py)**, a personal desktop assistant. Nova Browser works fully without them.

| File | What it adds to Nova |
|---|---|
| `section_13ZC_nova_browser_link.py` | A private link on `127.0.0.1:8766` (secret token, refuses web pages) so the browser's ✦ panel can chat with Nova, she can read the open page, and the browser can start her in the background (she still asks for her unlock code). |
| `section_13ZD_nova_browser_voice.py` | Lets Nova control the browser when you talk to her ("pause the video", "open my games"), answers from the browser's hubs ("what's the Lakers score"), and stops Nova's gaming mode from mistaking full-screen Nova Browser for a game. Needs 13ZC. |

They're written for Nova's section-based layout (paste above "SECTION 14 OF 14") and use her helper functions
(`nx_handler`, `nx_say`, `nx_strip`, …), so they won't run on their own.

> ⚠ **Never upload your assistant's own code (Jarvis.py).** It contains your unlock passphrase and tokens. Only these two
> sections are meant to be shared, and they don't contain any secrets.
