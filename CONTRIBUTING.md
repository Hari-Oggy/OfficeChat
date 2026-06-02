# Contributing to OfficeChat (Neuro AI)

First off, thank you for considering contributing to OfficeChat! It's people like you that make open-source software such a great community to learn, inspire, and create. 

Whether you're helping us fix bugs, improve the documentation, or spread the word, we'd love to have you as part of the community.

## 🚀 How Can I Contribute?

### 1. Reporting Bugs
If you find a bug, please check the [Issue Tracker](../../issues) to see if it has already been reported. If not, please open a new issue and include:
*   Your operating system and LibreOffice version.
*   Steps to reproduce the bug.
*   The expected behavior vs. what actually happened.
*   Relevant logs or error messages (usually printed to the console if LibreOffice is run via terminal).

### 2. Suggesting Enhancements
Have an idea for a new feature? We're all ears! Please open a feature request issue. Detail what the feature is, why it would be useful, and (if possible) how you envision it working within the LibreOffice UI.

### 3. Submitting Pull Requests
We gladly accept pull requests! If you're tackling an existing issue, please leave a comment on the issue saying you're working on it.

#### Development Workflow

1.  **Fork the Repository:** Fork the project to your own GitHub account and clone it locally.
    ```bash
    git clone https://github.com/YOUR_USERNAME/OfficeChat.git
    cd OfficeChat
    ```

2.  **Create a Branch:** Create a new branch for your feature or bug fix.
    ```bash
    git checkout -b feature/your-feature-name
    ```
    *Use descriptive names like `feature/add-calc-support` or `fix/markdown-parsing-bug`.*

3.  **Make Your Changes:** 
    *   **Keep it Zero-Dependency:** Remember our core architecture rule: *Do not introduce third-party `pip` dependencies* (like `requests` or `pydantic`). We rely strictly on Python's Standard Library (e.g., `urllib.request`) to prevent UNO environment crashes on Linux.
    *   **Follow the Structure:** Place native UNO UI logic in `src/oxt/pythonpath/extension/ui/` and core data logic in `core/`.

4.  **Test Your Changes:**
    Build the extension using the provided script and install it in LibreOffice to test.
    ```bash
    ./scripts/build_oxt.sh
    ```
    Install `build/Neuro_AI.oxt` via the LibreOffice Extension Manager.

5.  **Commit Your Changes:**
    Write clear, concise commit messages.
    ```bash
    git commit -m "feat: added spreadsheet context extraction"
    ```

6.  **Push and Open a PR:**
    ```bash
    git push origin feature/your-feature-name
    ```
    Open a Pull Request against the `main` branch of the original repository. Describe your changes clearly in the PR description.

## 🏗️ Project Structure Crash Course

*   `src/oxt/AI_Extension.py`: The main entry point. LibreOffice calls this file when a user clicks a button or uses a shortcut.
*   `src/oxt/Addons.xcu` & `AcceleratorKeys.xcu`: XML files that register the extension in LibreOffice's top menu and map keyboard shortcuts.
*   `src/oxt/pythonpath/extension/ui/`: Contains all the UI dialogs (e.g., `chat_dialog.py`).
*   `src/oxt/pythonpath/extension/core/`: Contains the heavy lifting for formatting (e.g., `rich_text.py` converts Markdown to native UNO styles).
*   `src/oxt/pythonpath/extension/ai/`: API providers (OpenAI, Google) and the async orchestrator.

## 📜 Code of Conduct
By participating in this project, you agree to maintain a welcoming, inclusive, and harassment-free environment for everyone. Please be respectful and constructive in issues and code reviews.

Thank you for helping make OfficeChat better!
