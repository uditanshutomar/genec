#!/bin/bash
# Test script to simulate what the VS Code extension does

echo "=== Testing GenEC CLI (simulating VS Code extension) ==="
echo ""

# Get the file path
FILE_PATH="/Users/uditanshutomar/commons-io/src/main/java/org/apache/commons/io/IOUtils.java"
REPO_PATH="/Users/uditanshutomar/commons-io"

echo "File: $FILE_PATH"
echo "Repo: $REPO_PATH"
echo ""

# Check if file exists
if [ ! -f "$FILE_PATH" ]; then
    echo "ERROR: File not found: $FILE_PATH"
    exit 1
fi

# Check if repo exists
if [ ! -d "$REPO_PATH" ]; then
    echo "ERROR: Repo not found: $REPO_PATH"
    exit 1
fi

echo "=== Step 1: Check if genec.cli is available ==="
python3 -m genec.cli --help > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✓ genec.cli is available"
else
    echo "✗ genec.cli is NOT available"
    exit 1
fi
echo ""

echo "=== Step 2: Check config file ==="
CONFIG_PATH="/Users/uditanshutomar/genec/genec/config/config.yaml"
if [ -f "$CONFIG_PATH" ]; then
    echo "✓ Config file exists: $CONFIG_PATH"
else
    echo "⚠ Config file not found: $CONFIG_PATH"
    echo "  Will use default config"
fi
echo ""

echo "=== Step 3: Run GenEC CLI (with verbose output) ==="
echo "Command: python3 -m genec.cli --target \"$FILE_PATH\" --repo \"$REPO_PATH\" --max-suggestions 3 --verbose"
echo ""

# Set API key if available
if [ ! -z "$ANTHROPIC_API_KEY" ]; then
    echo "✓ API key is set"
else
    echo "⚠ No API key set (set ANTHROPIC_API_KEY environment variable)"
fi
echo ""
echo "==================== OUTPUT ===================="
echo ""

# Run the command
python3 -m genec.cli \
    --target "$FILE_PATH" \
    --repo "$REPO_PATH" \
    --config "$CONFIG_PATH" \
    --max-suggestions 3 \
    --verbose

EXIT_CODE=$?
echo ""
echo "==================== END OUTPUT ===================="
echo ""
echo "Exit code: $EXIT_CODE"

if [ $EXIT_CODE -eq 0 ]; then
    echo "✓ GenEC completed successfully"
else
    echo "✗ GenEC failed with exit code $EXIT_CODE"
fi
