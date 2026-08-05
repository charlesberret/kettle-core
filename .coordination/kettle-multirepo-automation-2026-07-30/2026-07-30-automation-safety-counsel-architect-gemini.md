# Counsel (automation-safety) — architect-gemini

**Walls (Non-negotiable):**
- No unattended writes to `server.py`, `static/index.html`, `kettle_main.py`, `projects.json`, `settings.json`.
- Nothing binds or signals port 4242.
- No cross-repo push credentials or new always-on automation.

**Recommendations:**
- Automation should be restricted strictly to drift detection (verification) rather than generation (writing). 
- Preliminary ballot on G3: concur-with-qualification (safe to automate green-tier drift detection only).
