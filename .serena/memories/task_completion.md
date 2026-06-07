# Task Completion Checklist

## After Completing a Task
Since this project has no automated testing, linting, or formatting tools configured:

1. **Compile check**: `python3 -m py_compile *.py` (catches syntax errors)
2. **Runtime import check** (uses the venv with PyQt6/aiohttp):
   `harmony_env/bin/python -c "import harmony, harmony_gui, discovery_handlers, retry_utils, state_manager; print('OK')"`
3. **Check imports**: Ensure no circular imports were introduced; remove now-unused imports
4. **Verify async patterns**: All network operations should use async/await
5. **Check error handling**: Network operations use shared `retry_utils.async_retry` (see `mem:style_and_conventions`)
6. **Git commit**: Stage and commit with descriptive message. NOTE: `config.py` is gitignored (local-only), so config fixes won't appear in `git status`.

## No Automated Checks Available
- No test suite to run; no linter/formatter/CI configured
- `ruff`/`pyflakes`/`pytest` NOT installed in `harmony_env`

## Manual Testing Approach
- CLI: Run `./harmony.py <cmd>` (e.g. `status`, `vol+`)
- GUI: Launch via `./start_harmony_gui.sh` and verify UI behavior
- Discovery: `python harmony.py discover` to test hub communication
- For pure-logic changes (e.g. retry semantics), write a throwaway inline
  `harmony_env/bin/python - <<'EOF' ... EOF` script to assert behavior.
