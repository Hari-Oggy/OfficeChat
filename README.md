<div align="center">
  <img src="fig/officechat_logo.png" alt="OfficeChat Logo" width="250"/>
  <h1>OfficeChat (Neuro AI) for LibreOffice</h1>
  <p><strong>A production-grade AI Copilot extension integrated natively into LibreOffice Writer.</strong></p>
</div>

---

OfficeChat  brings advanced, context-aware AI capabilities directly into your LibreOffice documents. Operating flawlessly within LibreOffice's native UNO UI, it bridges powerful AI ecosystems (like OpenAI, Google Gemini, and Local Ollama) with seamless rich-text processing.

## ✨ Key Features

### 💬 Deep Context & Chat Interface
* **Native Modeless UI:** A draggable, floating chat dialog that doesn't block you from editing your document.
* **Document Awareness:** Automatically reads your highlighted text and document structure as context. Large documents are handled gracefully via intelligent **Smart Truncation**.
* **Dynamic Suggestions:** Real-time prompt suggestions change based on your active state (e.g., whether text is selected or the document is empty).
* **Live Streaming:** Watch the AI's response type out in real-time within the chat window.

### 🚀 Quick Action Engines
Leverage advanced content engines directly via keyboard shortcuts or UI buttons:
* **Rewrite Engine:** Generate 3 distinct variants of your selected text with customizable tones (Professional, Casual, Executive, Academic, Marketing, Technical).
* **Translate Engine:** Format-preserving markdown translation into 6+ languages.
* **Table Engine:** Instantly convert messy, unstructured text directly into clean markdown tables.
* **Document Engine:** Automatically generate Summaries, Action Items, Deadlines, and Tables of Contents.

### 📝 Native Rich-Text Formatting
* **Zero Markdown Artifacts:** The extension parses AI markdown responses and applies **native LibreOffice Writer styles**.
* Headings (`Heading 1`, `Heading 2`), lists, code blocks, and bold/italic formatting are applied instantly.
* **Native Tables:** Automatically detects markdown tables and builds native `com.sun.star.text.TextTable` objects directly in your document.

### ⚡ Global Keyboard Shortcuts
Accelerate your workflow with global LibreOffice hotkeys:
* `Ctrl`+`Shift`+`A`: Open AI Chat
* `Ctrl`+`Shift`+`R`: Rewrite Selection
* `Ctrl`+`Shift`+`S`: Summarize Selection
* `Ctrl`+`Shift`+`D`: Ask About Document

## 🔌 Universal Provider Support
Built completely on Python's Standard Library (Zero `pip` dependencies!), the extension is ultra-fast and crash-proof. It supports:
* **Google Gemini** (Gemini 2.5 Pro)
* **OpenAI** (GPT-4o)
* **Ollama** (Run models like Llama 3 or Gemma 100% locally and privately!)

---

## ⚙️ Setup & Installation

### 1. Build & Install
1. Clone the repository and build the extension:
   ```bash
   ./scripts/build_oxt.sh
   ```
2. Open LibreOffice and go to **Tools > Extension Manager**.
3. Click **Add**, select the `build/Neuro_AI.oxt` file, and restart LibreOffice.

### 2. Configuration
Upon first run (or clicking Open AI Chat), a configuration file is created automatically at:
* **Linux:** `~/.config/libreoffice_ai/config.json`
* **Windows/Mac:** Corresponding user config directories.

Open the JSON file and add your API keys. Change the `"active_provider"` to use your preferred model. 

#### Example `config.json`
```json
{
    "active_provider": "google",
    "providers": {
        "google": {
            "api_key": "YOUR_GEMINI_KEY",
            "model": "gemini-2.5-pro"
        },
        "openai": {
            "api_key": "YOUR_OPENAI_KEY",
            "model": "gpt-4o"
        },
        "ollama": {
            "api_key": "ollama",
            "model": "llama3",
            "base_url": "http://127.0.0.1:11434/v1"
        }
    }
}
```
*(Note: To use Ollama, simply define it under providers and set `active_provider` to `"ollama"` as shown above).*

---

## 🏗️ Architecture & Development

This project showcases **production-grade engineering patterns** for Python LibreOffice extensions:

* **Zero-Dependency Core:** Heavy libraries (`pydantic`, `httpx`) were intentionally stripped out in favor of Python's `urllib.request`. This solves notorious LibreOffice environment crashes on Linux.
* **Safe Async-to-Sync Bridging:** Demonstrates how to bridge async Python streams with synchronous UNO UI threads using a thread-safe message queue (`AsyncEngine`) and polling.
* **Modular Design:** Clear separation between core UNO integration, native dialog UI, AI providers, and robust Markdown parsing (`rich_text.py`).

### 📁 Directory Structure
```text
.
├── src/
│   └── oxt/
│       ├── AI_Extension.py    # Main UNO entry point & Dispatcher
│       ├── AcceleratorKeys.xcu# Global Keyboard Shortcuts
│       └── pythonpath/extension/
│           ├── core/          # Native Rich-Text, Document Context, Content Engines
│           ├── ui/            # Native UNO Chat Dialog & Prompt Suggestions
│           └── ai/            # API Providers (Google, OpenAI, Orchestrator)
├── scripts/                   # Build scripts (.oxt packaging)
└── docs/                      # Future Roadmaps (Calc Integration)
```

---

## 🤝 Contributing

We welcome contributions from the community! Whether it's adding new features (like Calc integration), fixing bugs, or improving documentation, we'd love your help.

Please read our [Contributing Guidelines](CONTRIBUTING.md) for details on how to set up your development environment, our zero-dependency architecture rule, and the process for submitting pull requests.

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
