# Changelog

All notable changes to **Code Review Platform** will be documented in this file.  
This project follows [Semantic Versioning](https://semver.org/):

- **MAJOR** – breaking changes / big feature jumps (2.0.0 → 3.0.0)
- **MINOR** – new features, no breaking changes (2.0.0 → 2.1.0)
- **PATCH** – bug fixes only (2.0.0 → 2.0.1)

---

## [2.0.0] – 2025-11-23

### 🔥 Major features

- Added **GitHub repository URL analysis**  
  - User can paste a GitHub repo URL.  
  - Backend automatically downloads the repository as a ZIP.  
  - All code files (`.py`, `.js`, `.java`, `.txt`, `.md`) are extracted and analysed.  
  - Each file gets its **own LLM review**, summary, issues, suggestions and score.  
  - Project detail page shows all files and their scores in one place.

- Added **AI Quick Suggestions panel** on the main review page  
  - New button **“AI quick suggestions”** runs a fast review of the code currently in the editor.  
  - Shows a short summary plus multiple focused suggestions (style, bugs, improvements).  
  - Does *not* create database entries – designed for live feedback while editing.

- Upgraded **live code editor** (Monaco) integration  
  - VS Code–style editor with syntax highlighting and dark theme.  
  - Language automatically switches with the selected language (Python / JS / Java / C / C++).  
  - Editor content is synced back to the Django form on submit.

- Improved **project review layout**  
  - Project detail page now shows **file names + quality scores**, including `0.0` scores.  
  - Clear “Project files & scores” list for navigating to per-file review pages.

### 🧹 Improvements

- Better validation when uploading ZIPs or using GitHub URLs (size limit, image detection, non-code files skipped).  
- More helpful error + info messages using Django messages framework.  
- Cleaner CSS for cards, buttons, mobile layout, and history list.

---

## [1.3.0] – 2025-11-22

### Features

- Added **per-file reviews for ZIP uploads**:  
  - A ZIP project can be uploaded.  
  - Each code file inside the ZIP is reviewed separately by the LLM.  
  - New project page lists all generated reviews for that submission.

- History page upgraded to show number of file reviews per submission.

---

## [1.2.0] – 2025-11-21

### Features

- Introduced **Monaco editor** for the main “Code” input:
  - Replaced plain `<textarea>` with a VS Code–like editor.
  - Added responsive height, dark theme and better typing experience.

---

## [1.1.0] – 2025-11-20

### Features

- Basic UI overhaul:
  - New card layout, navigation bar and footer.
  - Cleaner typography and spacing.
- Improved error handling and message display.

---

## [1.0.0] – 2025-11-19

### Initial release

- Core **Code Review Platform**:
  - Paste code or upload a single file.  
  - LLM (OpenAI / Anthropic) analyses code and returns JSON.  
  - Displays summary, issues, suggestions, test ideas and quality score.  
  - Review history page with links to past results.
