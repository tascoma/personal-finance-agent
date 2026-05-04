import os

# Provide a dummy key so Agent(...) construction succeeds at import time.
# Tests patch run_* functions directly, so this key is never sent to the API.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
