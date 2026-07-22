/**
 * Canonical sitting UI copy — single source for web, desktop (sidecar), and plugin.
 *
 * Served as /ui-copy.js → window.SETSWEEP_UI_COPY.
 * Plugin regenerates packages/vscode/src/uiCopy.ts via:
 *   npm run sync-ui-copy   (also precompile / package)
 * See docs/UI.md § Shared UI copy. Edit ONLY this file for sitting strings.
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
