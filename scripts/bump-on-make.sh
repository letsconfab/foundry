#!/bin/bash
# Wrapper script that checks if command matches make api/ui/all
# and bumps version if so

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

# Check if command contains make api, make ui, or make all
if echo "$COMMAND" | grep -qE 'make (api|ui|all)'; then
    /Users/sidd/Desktop/src/letsconfab/foundry/scripts/bump-patch-version.sh
fi

# Always exit 0 to allow the command to proceed
exit 0
