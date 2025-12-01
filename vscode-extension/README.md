# GenEC VS Code Extension

**GenEC (Generative Extract Class)** is an AI-powered refactoring tool that automatically identifies and extracts cohesive classes from large "God Classes" in Java.

This extension integrates the GenEC CLI directly into VS Code, allowing you to refactor your code with a single command.

## Features

*   **Automatic Cluster Detection**: Uses graph-based analysis to find cohesive groups of methods and fields.
*   **AI-Powered Naming**: Uses an LLM (Anthropic Claude) to suggest meaningful names for extracted classes.
*   **Robust Code Generation**: Uses Eclipse JDT to generate syntactically correct Java code.
*   **Verification**: Automatically verifies refactorings by running your project's build and tests.

## Prerequisites

1.  **Python 3.10+**: Ensure Python is installed.
2.  **GenEC CLI**: You must have the `genec` package installed in your Python environment.
    ```bash
    pip install genec
    ```
    *(Or `pip install -e .` if installing from source)*

## Usage

### Using the GenEC Sidebar (Recommended)

1.  Open a **Java file** in VS Code that you want to refactor.
2.  Click on the **GenEC icon** in the Activity Bar (sidebar).
3.  Enter your **Anthropic API Key** in the input field.
4.  Click the **"Refactor Current Class"** button.

The extension will run the GenEC pipeline and display the suggested refactorings directly in the sidebar.

### Using the Command Palette

1.  Open a **Java file** in VS Code that you want to refactor.
2.  Open the **Command Palette** (`Cmd+Shift+P` or `Ctrl+Shift+P`).
3.  Run the command: **`GenEC: Refactor Current Class`**.

The extension will run the GenEC pipeline in the background and notify you when the refactoring is complete. You can click **"Show Output"** to see detailed logs.

## Configuration

You can configure the extension in **Settings** (`Cmd+,`):

*   `genec.pythonPath`: Path to the Python interpreter where `genec` is installed (default: `python3`).
*   `genec.apiKey`: Your Anthropic API Key. If not set here, it will look for the `ANTHROPIC_API_KEY` environment variable.
