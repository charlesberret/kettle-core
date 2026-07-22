/**
 * Canonical sitting UI copy — single source for web (and desktop via sidecar).
 * Plugin: packages/vscode/src/uiCopy.ts must stay key-for-key identical
 * (see docs/UI.md § Shared UI copy). When you change a string, update both files
 * in the same change or the next parity pass will fail.
 *
 * Served as /ui-copy.js; window.SETSWEEP_UI_COPY after load.
 */
(function (root) {
  "use strict";
  var COPY = {
    /* Agent stream / chat */
    streamIdle: "Chat stream idle",
    chatPlaceholder: "Chat with the Setsweep agent…",
    chatPlaceholderFounding: "Chat with the Setsweep agent…",
    chatPlaceholderProposing: "Ask to revise the proposal — or edit it, then approve",

    /* Editor / mid chrome */
    editorPlaceholder: "select a file from the queue",
    editorPlaceholderFounding: "founding interview — work in the agent pane on the right",
    editorPlaceholderProposing: "desk proposal — edit, then approve to found",
    commentPlaceholder:
      "a note for the sweep, tied to this file — Enter saves · Shift+Enter newline · Esc cancels",

    /* Founding / empty states */
    foundingQueueHintTitle: "founding",
    foundingQueueHintBody:
      "The curator is in the agent pane. Answer there, then draft proposal ✓ when ready. " +
      "The queue fills after you approve the desk proposal.",
    proposingQueueHintTitle: "desk proposal",
    proposingQueueHintBody:
      "Edit the proposal in the center pane, then approve to found the desk and stock the first queue.",

    /* Add project */
    addProjectTitle: "add project",
    addProjectNote:
      "Name a folder under your home. The interview starts in the agent pane — finish ✓ drafts a proposal you edit and approve.",
    addProjectStart: "start interview",
  };
  root.SETSWEEP_UI_COPY = COPY;
  if (typeof module !== "undefined" && module.exports) module.exports = COPY;
})(typeof globalThis !== "undefined" ? globalThis : this);
