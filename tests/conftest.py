import os

# The suite hits rate-limited endpoints far faster than a real client would. Rate-limit tests
# switch it back on with monkeypatch.
os.environ.setdefault("SPENDIQ_RATE_LIMIT", "0")
