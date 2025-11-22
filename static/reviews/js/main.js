// static/reviews/js/main.js

document.addEventListener("DOMContentLoaded", function() {
  /* ================= COPY BUTTONS ================= */
  document.querySelectorAll(".copy-btn").forEach(btn => {
    btn.addEventListener("click", async () => {
      const target = btn.dataset.target;
      const el = document.getElementById(target);
      if (!el) return;
      const text = el.innerText || el.textContent;
      try {
        await navigator.clipboard.writeText(text);
        const old = btn.innerText;
        btn.innerText = "Copied";
        setTimeout(()=> btn.innerText = old, 1500);
      } catch(e) {
        alert("Copy failed. Select and copy manually.");
      }
    });
  });

  /* ================= FORM SUBMIT SPINNER ================= */
  const form = document.getElementById("review-form");
  if (form) {
    form.addEventListener("submit", function(){
      const btn = document.getElementById("submit-btn");
      const txt = document.getElementById("btn-text");
      const spinner = document.getElementById("btn-spinner");
      if (btn) {
        btn.disabled = true;
        if (spinner) spinner.style.display = "inline-block";
        if (txt) txt.innerText = "Reviewing…";
      }
    });
  }

  /* ================= UPLOAD PREVIEW ================= */
  const uploadInput = document.querySelector("input[type=file]");
  const uploadInfo = document.getElementById("upload-info");
  if (uploadInput && uploadInfo) {
    uploadInput.addEventListener("change", function(){
      const f = uploadInput.files[0];
      if (!f) {
        uploadInfo.innerText = "";
        return;
      }
      uploadInfo.innerText = `Selected: ${f.name} — ${(f.size/1024).toFixed(1)} KB`;
    });
  }

  /* ================= MONACO CODE EDITOR ================= */

  const textarea = document.getElementById("id_code");
  const editorContainer = document.getElementById("editor");
  const langSelect = document.getElementById("id_language");

  // If not on index page, or elements missing, do nothing
  if (textarea && editorContainer) {
    function mapLanguage(djangoLang) {
      switch (djangoLang) {
        case "python": return "python";
        case "javascript": return "javascript";
        case "java": return "java";
        case "c": return "c";
        case "cpp": return "cpp";
        default: return "plaintext";
      }
    }

    // Monaco loader should define "require" globally
    if (typeof require === "undefined") {
      console.warn("Monaco loader not available (require undefined). Falling back to textarea.");
    } else {
      require.config({
        paths: {
          'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs'
        }
      });

      require(['vs/editor/editor.main'], function() {
        // Hide textarea once editor is ready
        textarea.style.display = "none";

        const monacoEditor = monaco.editor.create(editorContainer, {
          value: textarea.value || "",
          language: mapLanguage(langSelect ? langSelect.value : "python"),
          theme: "vs-dark",
          automaticLayout: true,
          fontSize: 14,
          minimap: { enabled: false },
          scrollBeyondLastLine: false,
        });

        // On form submit, sync editor content back to textarea
        if (form) {
          form.addEventListener("submit", function() {
            textarea.value = monacoEditor.getValue();
          });
        }

        // Update language when select changes
        if (langSelect) {
          langSelect.addEventListener("change", function() {
            monaco.editor.setModelLanguage(
              monacoEditor.getModel(),
              mapLanguage(langSelect.value)
            );
          });
        }
      });
    }
  }

  /* ================= FILE TREE BUILDER ================= */

  const treeContainer = document.getElementById("file-tree");
  const rawList = document.getElementById("raw-file-list");

  if (treeContainer && rawList) {
    // Build a tree data structure from the <li> items
    const root = { type: "folder", name: "(root)", children: {} };

    const items = rawList.querySelectorAll("li[data-file-path]");
    items.forEach(li => {
      const path = li.dataset.filePath || "(root code)";
      const url = li.dataset.reviewUrl;
      const score = li.dataset.score || "";
      const parts = path.split("/").filter(Boolean);

      let current = root;
      if (parts.length === 0) {
        parts.push("(root code)");
      }

      parts.forEach((part, index) => {
        if (!current.children[part]) {
          current.children[part] = {
            type: index === parts.length - 1 ? "file" : "folder",
            name: part,
            children: {},
            url: null,
            score: null
          };
        }
        current = current.children[part];
      });

      if (current.type === "file") {
        current.url = url;
        current.score = score;
      }
    });

    function renderNode(node, container) {
      const ul = document.createElement("ul");

      Object.keys(node.children).sort().forEach(key => {
        const child = node.children[key];
        const li = document.createElement("li");

        if (child.type === "folder") {
          li.className = "tree-folder";

          const header = document.createElement("div");
          header.className = "tree-folder-header";

          const toggle = document.createElement("span");
          toggle.className = "tree-toggle";
          toggle.textContent = "▸";

          const nameSpan = document.createElement("span");
          nameSpan.textContent = child.name;

          header.appendChild(toggle);
          header.appendChild(nameSpan);
          li.appendChild(header);

          const childrenContainer = document.createElement("div");
          childrenContainer.className = "tree-children";
          renderNode(child, childrenContainer);
          li.appendChild(childrenContainer);

          // toggle open/close
          header.addEventListener("click", () => {
            li.classList.toggle("open");
          });
        } else {
          li.className = "tree-file";
          const link = document.createElement("a");
          link.href = child.url || "#";
          link.textContent = child.name;
          li.appendChild(link);

          if (child.score) {
            const badge = document.createElement("span");
            badge.className = "tree-file-score";
            badge.textContent = child.score;
            li.appendChild(badge);
          }
        }

        ul.appendChild(li);
      });

      container.appendChild(ul);
    }

    // Render the tree into the container
    renderNode(root, treeContainer);
  }

});
