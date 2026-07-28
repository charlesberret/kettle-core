/**
 * Canonical sitting UI copy — single source for web, desktop, and VS Code.
 *
 * Served as /ui-copy.js → window.KETTLE_UI_COPY.
 * kettle-vscode regenerates src/uiCopy.ts via:
 *   KETTLE_SRC=../kettle-core npm run sync-ui-copy
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
    chatPlaceholder: "Chat with the Kettle agent…",
    chatPlaceholderFounding: "Chat with the Kettle agent…",
    chatPlaceholderProposing: "Ask to revise the proposal — or edit it, then Found Desk",

    /* Editor / mid chrome */
    editorPlaceholder: "",
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
    /** Second line of Desk brief when a project is bound but no queue entry is selected. */
    noEntryBriefBody:
      "The Kettle file panel contains a batch of files for you to review, edit, approve, and sweep when the batch is finished.",

    /* Add project */
    addProjectTitle: "Add Project",
    addProjectNote:
      "Name a folder under your home. The interview starts in the agent pane — finish ✓ drafts a proposal you edit, then use Found Desk.",
    addProjectStart: "Start Interview",
  };
  root.KETTLE_UI_COPY = COPY;
  if (typeof module !== "undefined" && module.exports) module.exports = COPY;
})(typeof globalThis !== "undefined" ? globalThis : this);
