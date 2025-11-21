# 🧠 Code Review Platform  
### AI-Powered Automated Code Review using OpenAI / Anthropic LLMs  
Modern, secure, and beautifully designed platform for analyzing programming code with the help of Large Language Models.

---

## 🚀 Overview  
**Code Review Platform** is a Django-based web application that performs **automated code review** using advanced AI models such as **OpenAI GPT** and **Anthropic Claude**.  
Users can paste code or upload supported files (.py, .js, .java, .txt), and the system provides:

- 🔍 Bug detection  
- 🛡 Security risk analysis  
- ⚡ Performance suggestions  
- 🎨 Code style improvements  
- 🧪 Test case recommendations  
- 📊 Code quality score  
- 📝 Structured JSON output  

This project is ideal for **students**, **developers**, **researchers**, and **teams** who want an AI-based smart code auditor.

---

## ✨ Features

### 🔥 Core Features
- AI-powered code review using LLMs (GPT / Claude)  
- Supports multiple languages (Python, JavaScript, Java, C, C++)  
- Secure file upload with imghdr detection  
- Smart error handling and JSON extraction  
- High-quality modern UI (Inter font + responsive + clean layout)  

### 🛡 Safety Layers
- Image detection (prevents sending PNG/JPG to LLM)  
- File size limits  
- Extension validation  
- Environment variable–based LLM keys  
- Error messages + graceful fallbacks  

### 💡 UI/UX Improvements
- Syntax highlighting (highlight.js)  
- Copy patch / raw JSON buttons  
- Upload preview  
- Smooth loading button with spinner  
- Dark theme code blocks  

### 📜 Additional Features
- Review history page  
- Clean code structure  
- Model-independent (switch provider easily)  
- Future-ready for GitHub integration, CI/CD, Docker  

---

## 🛠 Tech Stack

| Layer            | Technology |
|-----------------|------------|
| Backend         | Django (Python) |
| Frontend        | HTML, CSS, JS, Highlight.js |
| AI Models       | OpenAI GPT / Anthropic Claude |
| Database        | SQLite (default) |
| Security        | python-dotenv, imghdr |
| Deployment      | Render, PythonAnywhere, Heroku (supported) |

---

## 📂 Project Structure


