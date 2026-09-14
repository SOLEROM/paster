/**
 * paster — terminal glue (solBench/webterm). Loaded only when the server set
 * use_webterm. A module, so it runs after every classic script and before
 * DOMContentLoaded: globals it needs (currentTheme, toast) exist, and
 * main.js has not booted yet.
 */
import { WebTerm } from '/webterm/static/webterm.js';

const wt = new WebTerm({
  root: '#webterm-root',
  theme: () => (typeof currentTheme === 'function' ? currentTheme() : 'dark'),
  onError: (msg) => toast(msg, 'warn'),
  placeholder: 'No sessions. Shell in the repo above, or + in the strip.',
});

// 4ColThems announces switches; the terminal canvas cannot read CSS tokens.
window.addEventListener('themechange', () => wt.refreshTheme());
// Land the caret in the terminal when its view is shown.
document.addEventListener('viewchange', (e) => {
  if (e.detail.view === 'sessions' && typeof wt.focusActive === 'function') wt.focusActive();
});

await wt.mount();

// "Shell in the repo": the session the strip's + opens as well (the server's
// resolver ignores the payload and always starts in the checkout), as a
// labelled button so the entry point is obvious.
const shellBtn = document.getElementById('btn-shell-repo');
if (shellBtn) shellBtn.addEventListener('click', () => { wt.createSession({ kind: 'workspace' }); });
window.wt = wt;   // console access for debugging
