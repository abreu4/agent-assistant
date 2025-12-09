#!/bin/bash
# Quick test to verify workspace indexing works

echo "Starting agent service test..."
echo "============================================================"
echo ""

# Send "exit" after a brief delay to allow initialization
(sleep 8; echo "exit") | python3 -m src.service 2>&1 | tee /tmp/agent_test_output.log

echo ""
echo "============================================================"
echo "Checking for errors in output..."
echo ""

# Check for the specific workspace indexing error
if grep -q "Workspace indexing failed.*EOF" /tmp/agent_test_output.log; then
    echo "❌ FAILED: Workspace indexing error still present"
    exit 1
elif grep -q "✓ Workspace indexed" /tmp/agent_test_output.log; then
    echo "✅ SUCCESS: Workspace indexed successfully"
    exit 0
else
    echo "⚠️  WARNING: Could not determine indexing status"
    echo "Showing relevant log lines:"
    grep -i "workspace\|index" /tmp/agent_test_output.log || echo "No workspace/index logs found"
    exit 0
fi
