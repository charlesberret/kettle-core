---
id: 09
title: Allowlist sanitizer + keyboard access
repo: setsweep-core
touches: [static/index.html, static/ (vendored DOMPurify)]
risk: run-critical
depends-on: [08]
status: done
---

## Context

`sanitizeRender` (index.html:1413–1421) is a blocklist — it strips script/iframe/object/
embed/link/style tags, `on*` attributes, and `javascript:` hrefs, and nothing else.
Rendered content is arbitrary markdown from swept project folders, and the page can call
file-write APIs, so a hostile file in a reviewed folder is an XSS-to-file-write chain:
blocklists always lose (formaction, data: URIs, SVG event surfaces are already through).
Separately, accessibility is below any public floor: the streaming chat has no aria-live
region, urgency is color-only dots, four modal overlays (addbg/setupbg/sweepbg/admin)
have no focus trap or aria-modal, and the queue is unusable without a pointer (qitem
divs with onclick, no tabindex).

## Task

1. Vendor DOMPurify (single local file, ~7 KB gzipped — consistent with the local-only,
   no-CDN philosophy; add to the third-party notices in the README). Replace
   `sanitizeRender`'s body with a DOMPurify call using a conservative allowlist profile;
   keep the function name and call sites.
2. Accessibility floor, four targeted changes:
   - `aria-live="polite"` wrapper on the chat stream (throttle: announce per message,
     not per token).
   - Queue keyboard path: `tabindex="0"` on entries, Enter opens, arrow keys move,
     visible focus ring.
   - Focus traps + `aria-modal="true"` + Esc on the four overlays.
   - Urgency dots gain a text/shape signal (letter or label), not color alone.

## Constraints

- After brief 08 only (its boot script and syntax gate protect this edit).
- No visual redesign — this is a safety-and-access pass, not a restyle.
- Markdown rendering behavior for honest content must not visibly change; keep a small
  corpus of real briefs/chat output and eyeball before/after.

## Done when

- An injection corpus (script tag, img onerror, formaction, data: URI link, SVG onload)
  renders inert in reading view and chat.
- A full sitting — select entry, read, comment, approve, sweep — is possible without
  touching the pointer.
- VoiceOver announces streaming replies and modal opens.

## Verify

Manual pass with the corpus file in a scratch project; keyboard-only walkthrough;
`node --check` gate from brief 08 still green; full pytest suite (server-side unaffected).

## Afterwards

`status: done`; README third-party notices updated; RELEASE.md usability gates reference
the keyboard walkthrough as a standing check.
