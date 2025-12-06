# Building GenEC Distribution

This guide explains how to build the standalone distribution of GenEC, which bundles the Python backend and Java dependencies for a zero-configuration user experience.

## Prerequisites

- Python 3.10+
- Maven 3.6+ (for building JDT wrapper)
- PyInstaller (`pip install pyinstaller`)

## Build Steps

### 1. Build JDT Wrapper

First, ensure the Java wrapper is built:

```bash
cd genec-jdt-wrapper
mvn clean package
cd ..
```

### 2. Build Python Executable

Run the build script to create the standalone executable:

```bash
python scripts/build_dist.py
```

This will create `dist/genec` (or `dist/genec.exe` on Windows).

### 3. Package VS Code Extension

Copy the built executable to the extension's distribution folder:

```bash
mkdir -p vscode-extension/dist
cp dist/genec vscode-extension/dist/
```

Then package the extension:

```bash
cd vscode-extension
npm install
vsce package
```

## How it Works

- **PyInstaller**: Bundles the Python interpreter, `genec` package, and all dependencies (NetworkX, etc.) into a single binary.
- **Data Bundling**: The `config/` directory and the JDT wrapper JAR are bundled inside the binary.
- **Runtime Detection**: The VS Code extension detects the presence of `dist/genec` and uses it instead of the system `python3`.
