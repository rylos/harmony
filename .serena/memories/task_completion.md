# Task Completion Checklist

## After Completing a Task
Since this project has no automated testing, linting, or formatting tools configured:

1. **Manual verification**: Test the modified functionality via CLI or GUI
2. **Check imports**: Ensure no circular imports were introduced
3. **Verify async patterns**: All network operations should use async/await
4. **Check error handling**: Network operations should have retry/timeout handling
5. **Git commit**: Stage and commit changes with descriptive message

## No Automated Checks Available
- No test suite to run
- No linter configured
- No formatter configured
- No CI/CD pipeline

## Testing Approach
- CLI: Run `./harmony.py` with relevant commands
- GUI: Launch via `./start_harmony_gui.sh` and verify UI behavior
- Discovery: Run `python harmony.py discover` to test hub communication
