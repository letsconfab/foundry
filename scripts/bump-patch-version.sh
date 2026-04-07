#!/bin/bash
# Bump patch version for API and UI before build/restart
# Used as a pre-build hook for Claude Code

set -e

FOUNDRY_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Bump API version in main.py
API_FILE="$FOUNDRY_ROOT/api/main.py"
if [ -f "$API_FILE" ]; then
    # Extract current version and bump patch
    current=$(grep -oP 'version="\K[0-9]+\.[0-9]+\.[0-9]+' "$API_FILE" | head -1)
    if [ -n "$current" ]; then
        IFS='.' read -r major minor patch <<< "$current"
        new_version="$major.$minor.$((patch + 1))"
        sed -i.bak "s/version=\"$current\"/version=\"$new_version\"/" "$API_FILE"
        rm -f "$API_FILE.bak"
        echo "API: $current -> $new_version"
    fi
fi

# Bump UI version in package.json
UI_FILE="$FOUNDRY_ROOT/ui/package.json"
if [ -f "$UI_FILE" ]; then
    current=$(grep -oP '"version": "\K[0-9]+\.[0-9]+\.[0-9]+' "$UI_FILE" | head -1)
    if [ -n "$current" ]; then
        IFS='.' read -r major minor patch <<< "$current"
        new_version="$major.$minor.$((patch + 1))"
        sed -i.bak "s/\"version\": \"$current\"/\"version\": \"$new_version\"/" "$UI_FILE"
        rm -f "$UI_FILE.bak"
        echo "UI: $current -> $new_version"
    fi
fi
