# Neuro AI - LibreOffice Extension

A production-grade **LibreOffice UNO extension** that integrates advanced AI capabilities directly into your documents. It provides an interactive, Copilot-like chat experience natively inside LibreOffice Writer and Calc, seamlessly bridging asynchronous Python AI ecosystems with LibreOffice's synchronous C++ UNO API.

## 🌟 Key Features

### 💬 Copilot-Like Chat UI
- **Native Floating Window:** A fully draggable, minimizable, and maximizable chat dialog that floats over your workspace.
- **Context Awareness:** Automatically reads your highlighted text and feeds it to the AI as context.
- **Quick Action Toolbar:** One-click buttons to *Rewrite, Improve, Summarize, Expand, Shorten, Format (Formal/Casual), Translate,* and *Fix Grammar*.
- **Live Streaming:** Watch the AI's response type out in real-time within the chat window.

### 📝 Native Rich-Text Formatting (Zero Markdown Artifacts)
- **UNO Rich Text Converter:** The extension doesn't just dump plain text. It parses the AI's markdown response and applies **native LibreOffice Writer styles**.
- Headings (`Heading 1`, `Heading 2`), lists (`List Bullet`, `List Number`), blockquotes, code blocks, and inline formatting (bold/italic) are applied flawlessly.
- **Table Generation:** Automatically detects markdown tables and builds actual native `com.sun.star.text.TextTable` objects directly in your document.
- **Insert vs Replace:** Choose to append the AI's content at your cursor, or completely replace the text you currently have highlighted.

### 🔌 Universal AI Support
The extension is built completely on Python's Standard Library (Zero `pip` dependencies in the compiled `.oxt`!) making it ultra-fast, cross-platform, and crash-proof. It supports:
- **Ollama**: Run models (Llama 3, Gemma) 100% locally and privately.
- **Groq**: Ultra-fast open-source model inference.
- **OpenRouter**: Access hundreds of open-source and proprietary models.
- **Google GenAI / Gemini**: Direct integration with Google's latest models.
- **OpenAI**: ChatGPT 4o / o1 support.

## ⚙️ Setup & Installation

1. Download or build the extension:
   ```bash
   ./scripts/build_oxt.sh
   ```
2. Open LibreOffice and go to **Tools > Extension Manager**.
3. Click **Add**, select the `build/Neuro_AI.oxt` file, and restart LibreOffice.
4. On Linux, the configuration file is automatically created at `~/.config/libreoffice_ai/config.json`.
5. Open the JSON file, add your API keys, and change the `"active_provider"` to your provider of choice (e.g., `"ollama"`, `"groq"`, `"openai"`).

## 🏗️ Architecture Highlights

This project showcases **production-grade engineering patterns** for Python LibreOffice extensions:

- **Zero-Dependency Core:** All heavy libraries (`pydantic`, `httpx`) were intentionally stripped out in favor of Python's `urllib.request`. This solves the notoriously difficult Linux/LibreOffice `_pydantic_core.so` environment crash.
- **Safe Async-to-Sync Bridging:** Demonstrates how to bridge async Python streams with synchronous UNO UI threads using a thread-safe message queue (`AsyncEngine`) and polling.
- **Modular Design:** Clear separation between core UNO integration, native dialog UI, AI providers, and robust Markdown parsing (`rich_text.py`).

## 📁 Directory Structure

```text
.
├── src/                   # Source code
│   └── oxt/
│       ├── AI_Extension.py    # Main UNO entry point
│       ├── Addons.xcu         # LibreOffice Top Menu Registration
│       └── pythonpath/extension/
│           ├── core/          # Native Rich-Text Converter & Thread bridging
│           ├── ui/            # Native UNO Chat Dialog & Listeners
│           ├── ai/            # API Providers (Google, OpenAI, Groq, Ollama)
│           └── utils/         # Async engine & config managers
├── scripts/               # Build scripts (.oxt packaging)
└── docs/                  # User documentation
```
