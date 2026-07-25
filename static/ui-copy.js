/**
 * Canonical sitting UI copy — single source for web, desktop (sidecar), and plugin.
 *
 * Served as /ui-copy.js → window.SETSWEEP_UI_COPY.
 * Plugin regenerates packages/vscode/src/uiCopy.ts via:
 *   npm run sync-ui-copy   (explicit maintainer action)
 * See docs/UI.md § Shared UI copy. Edit ONLY this file for sitting strings.
 *
 * Titles / heds / subheds: Title Case. Body copy and button labels: sentence case
 * or lowercase per docs/UI.md.
 */
(function (root) {
  "use strict";
  var COPY = {
    /* Agent stream / chat */
    streamIdle: "Chat stream idle",
    chatPlaceholder: "Chat with the Setsweep agent…",
    chatPlaceholderFounding: "Chat with the Setsweep agent…",
    chatPlaceholderProposing: "Ask to revise the proposal — or edit it, then Found Desk",

    /* Editor / mid chrome */
    editorPlaceholder: "select a file from the queue",
    editorPlaceholderFounding: "Founding Interview — work in the agent pane on the right",
    editorPlaceholderProposing: "Desk Proposal — edit, then use Found Desk",
    commentPlaceholder:
      "a note for the sweep, tied to this file — Enter saves · Shift+Enter newline · Esc cancels",

    /* Founding / empty states */
    foundingQueueHintTitle: "Founding",
    foundingQueueHintBody:
      "The curator is in the agent pane. Answer there, then Draft Proposal ✓ when ready. " +
      "The queue fills after you use Found Desk on the proposal.",
    proposingQueueHintTitle: "Desk Proposal",
    proposingQueueHintBody:
      "Edit the proposal in the editor until it matches your project, needs, and expectations. " +
      "Chat with the curator to revise or co-write. Press Found Desk only when it feels right — that founds the desk and stocks the first queue.",

    /* Add project */
    addProjectTitle: "Add Project",
    addProjectNote:
      "Name a folder under your home. The interview starts in the agent pane — finish ✓ drafts a proposal you edit, then use Found Desk.",
    addProjectStart: "Start Interview",
  };
  root.SETSWEEP_UI_COPY = COPY;
  if (typeof module !== "undefined" && module.exports) module.exports = COPY;
})(typeof globalThis !== "undefined" ? globalThis : this);
