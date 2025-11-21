// static/reviews/js/main.js
document.addEventListener("DOMContentLoaded", function() {
  // Copy buttons
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

  // Form submit spinner
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

  // Upload preview
  const uploadInput = document.querySelector("input[type=file]");
  const uploadInfo = document.getElementById("upload-info");
  if (uploadInput && uploadInfo) {
    uploadInput.addEventListener("change", function(){
      const f = uploadInput.files[0];
      if (!f) { uploadInfo.innerText = ""; return; }
      uploadInfo.innerText = `Selected: ${f.name} — ${(f.size/1024).toFixed(1)} KB`;
    });
  }
});
