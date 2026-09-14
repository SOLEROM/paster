// paster — the Help view: page tree + markdown reader over man/ (the skeleton's docs.js).
"use strict";

const help = { tree: [], current: null };

function helpTitle(name) {
  // "03-links.md" reads as "links": the numeric prefix only orders the files.
  return name.replace(/\.md$/i, "").replace(/^\d+[-_]/, "").replace(/[-_]/g, " ");
}

function firstHelpPage(nodes) {
  // index.md first when it exists; otherwise the first file, depth-first.
  const index = nodes.find((n) => n.type === "file" && /^index\.md$/i.test(n.name));
  if (index) return index.path;
  for (const n of nodes) {
    if (n.type === "file") return n.path;
    const inner = firstHelpPage(n.children || []);
    if (inner) return inner;
  }
  return null;
}

function helpTreeHtml(nodes) {
  return `<ul>${nodes.map((n) => n.type === "dir"
    ? `<li class="help-dir"><span class="help-label">${esc(helpTitle(n.name))}</span>${helpTreeHtml(n.children || [])}</li>`
    : `<li class="help-file ${n.path === help.current ? "active" : ""}" data-path="${esc(n.path)}">
         <span class="help-label">${esc(helpTitle(n.name))}</span></li>`).join("")}</ul>`;
}

function renderHelpTree() {
  $("#help-tree-list").innerHTML = helpTreeHtml(help.tree);
  $$("#help-tree-list .help-file").forEach((li) =>
    li.addEventListener("click", () => openHelpPage(li.dataset.path)));
}

async function openHelpPage(path) {
  const target = $("#help-content");
  try {
    const data = await api(`/api/help/page?file=${encodeURIComponent(path)}`);
    help.current = path;
    renderMarkdown(target, data.content);
    interceptMarkdownLinks(target, path, openHelpPage);
    renderHelpTree();
    target.scrollTop = 0;
  } catch (err) {
    target.innerHTML = `<p class="form-error">${esc(err.message)}</p>`;
  }
}

async function loadHelp() {
  const data = await api("/api/help/tree");
  help.tree = data.tree || [];
  renderHelpTree();
  const first = help.current || firstHelpPage(help.tree);
  if (first) await openHelpPage(first);
  else $("#help-content").innerHTML = `<p class="empty">No docs yet — add markdown files under man/.</p>`;
}

function setupHelp() {
  $("#btn-help-refresh").addEventListener("click", () => loadHelp().catch((e) => toastError("Docs failed", e)));
  wireButton($("#help-tree-toggle"), () => {
    const collapsed = $("#help-tree").classList.toggle("collapsed");
    $("#help-tree-toggle").setAttribute("aria-expanded", String(!collapsed));
    store("help-tree-hidden", collapsed ? "1" : "0");
  });
  if (restore("help-tree-hidden") === "1") {
    $("#help-tree").classList.add("collapsed");
    $("#help-tree-toggle").setAttribute("aria-expanded", "false");
  }
}
