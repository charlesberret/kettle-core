# Third-party notices

kettle bundles the following assets, each under its own license:

- **marked** v12.0.2 (`static/marked.min.js`) — a Markdown parser, MIT License.
  https://github.com/markedjs/marked
  Pinned vendored build: `marked@12.0.2` from https://registry.npmjs.org/marked
- **DOMPurify** v3.4.17 (`static/purify.min.js`) — HTML sanitizer (allowlist XSS
  defense for rendered markdown), dual-licensed Apache-2.0 OR MPL-2.0.
  https://github.com/cure53/DOMPurify
  Pinned vendored build: `dist/purify.min.js` from the `dompurify@3.4.17` npm tarball
  (https://registry.npmjs.org/dompurify).
- **IBM Plex** fonts (`static/fonts/*.woff2`) — SIL Open Font License 1.1.
  https://github.com/IBM/plex

Their licenses permit redistribution; this file preserves the required attribution.
kettle itself is MIT-licensed — see `LICENSE`.
