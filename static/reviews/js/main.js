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
    form.addEventListener("submit", function(e){
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
      if (!f) { uploadInfo.innerText = ""; return; }
      uploadInfo.innerText = `Selected: ${f.name} — ${(f.size/1024).toFixed(1)} KB`;
    });
  }

  /* ================= MONACO CODE EDITOR ================= */

  const textarea = document.getElementById("id_code");
  const editorContainer = document.getElementById("editor");
  const langSelect = document.getElementById("id_language");

  if (!textarea || !editorContainer || typeof require === "undefined") {
    // If something is missing, keep normal textarea usage.
    return;
  }

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

  // Configure Monaco loader
  require.config({
    paths: {
      'vs': 'https://cdnjs.cloudflare.com/ajax/libs/monaco-editor/0.44.0/min/vs'
    }
  });

  require(['vs/editor/editor.main'], function() {
    // Hide original textarea (keep as fallback)
    textarea.style.display = "none";

    // Create Monaco editor
    const monacoEditor = monaco.editor.create(editorContainer, {
      value: textarea.value || "",
      language: mapLanguage(langSelect ? langSelect.value : "python"),
      theme: "vs-dark",
      automaticLayout: true,
      fontSize: 14,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
    });

    // On form submit, copy Monaco content back into textarea so Django gets it
    if (form) {
      form.addEventListener("submit", function() {
        textarea.value = monacoEditor.getValue();
      });
    }

    // Change language dynamically when select changes
    if (langSelect) {
      langSelect.addEventListener("change", function() {
        monaco.editor.setModelLanguage(
          monacoEditor.getModel(),
          mapLanguage(langSelect.value)
        );
      });
    }
  });
});
