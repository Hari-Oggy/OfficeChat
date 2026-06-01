# Neuro AI LibreOffice Extension - User Guide

Welcome to the Neuro AI LibreOffice Extension! This extension brings the power of advanced AI models (like Google GenAI and OpenAI) directly into your LibreOffice Writer and Calc workflows natively and seamlessly.

This guide will walk you through installing the extension, securely configuring your API keys, and using the AI features.

---

## 1. Installation

The extension is packaged as a standard LibreOffice `.oxt` file.

1. Locate the built extension file: `build/Neuro_AI.oxt`.
2. Open **LibreOffice**.
3. In the top menu bar, navigate to **Tools > Extension Manager...**.
4. Click the **Add** button at the bottom of the window.
5. Select the `Neuro_AI.oxt` file from your system.
6. Accept any license agreements if prompted and wait for the installation to finish.
7. **Restart LibreOffice** (close all open LibreOffice windows and open it again) to ensure the new menus load correctly.

---

## 2. Configuration & API Keys

For security, your API keys are stored locally on your machine in a protected configuration file, rather than inside the LibreOffice UI. 

When you run the extension for the very first time, it will automatically generate a configuration file at:
`~/.config/libreoffice_ai/config.json`

### Setting up your keys:
1. Open a terminal or your favorite text editor.
2. Open the file `~/.config/libreoffice_ai/config.json`. If it hasn't been generated yet, you can create it manually with the structure below.
3. Add your API keys for the providers you wish to use. You can also change the `active_provider` to switch between models.

**Example `config.json`:**
```json
{
    "active_provider": "ollama",
    "providers": {
        "openai": {
            "api_key": "sk-your-openai-api-key-here",
            "model": "gpt-4o"
        },
        "google": {
            "api_key": "AIzaSy-your-google-api-key-here",
            "model": "gemini-1.5-pro"
        },
        "groq": {
            "api_key": "gsk_your_groq_api_key_here",
            "model": "llama3-70b-8192"
        },
        "openrouter": {
            "api_key": "sk-or-your_openrouter_api_key_here",
            "model": "meta-llama/llama-3-8b-instruct:free"
        },
        "ollama": {
            "api_key": "ollama",
            "model": "llama3",
            "base_url": "http://localhost:11434/v1"
        }
    }
}
```

### Supported Providers
- **Google GenAI**: Use `"active_provider": "google"`
- **OpenAI**: Use `"active_provider": "openai"`
- **Groq**: Use `"active_provider": "groq"` (Ultra-fast open-source models)
- **OpenRouter**: Use `"active_provider": "openrouter"` (Access to hundreds of free and paid models)
- **Ollama**: Use `"active_provider": "ollama"` (Run models 100% locally on your machine for privacy)

*Note: Make sure to keep this file secure. The extension attempts to set the file permissions to `600` (read/write only by your user) automatically.*

---

## 3. Using the Extension in Writer

The extension adds a new **"Neuro AI"** menu to your top toolbar.

### AI Text Generation & Summarization
1. Open a LibreOffice Writer document.
2. **Contextual Action:** Highlight a specific paragraph or sentence you want to modify (e.g., to summarize or improve it).
3. If no text is highlighted, the AI will generate creative text at the end of your document.
4. Click **Neuro AI > AI Text Generation...** from the top menu.
5. The AI will process your request in the background, and you will see the generated text stream directly into your document!

---

## 4. Using the Extension in Calc

You can also use the AI to analyze spreadsheet data.

### AI Data Processing
1. Open a LibreOffice Calc spreadsheet.
2. Click on a specific cell containing data you want to analyze.
3. Click **Neuro AI > AI Data Processing...** from the top menu.
4. The AI will read the value of the active cell, generate insights or analysis, and append its response directly into the cell.
5. If the cell is empty, the AI will provide a fun spreadsheet fact!

---

## Troubleshooting

- **"ModuleNotFoundError" or Missing Dependencies:** The extension comes pre-bundled with its dependencies. Ensure you didn't extract the `.oxt` manually. Always install it via the Extension Manager.
- **The "Neuro AI" Menu doesn't appear:** Ensure you completely restarted LibreOffice after installation. Sometimes background LibreOffice processes stay open. You can force close them on Linux using `killall soffice.bin` in the terminal.
- **No Text is Generated:** Double-check your `config.json` file. Ensure the `active_provider` is spelled correctly (`openai` or `google`) and that your API keys are valid and have sufficient quota.
