import os
from pathlib import Path

TEST_DB = Path("/tmp/ai-customer-support-platform-test.db")
TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["AI_PROVIDER"] = "template"
os.environ.pop("OPENAI_API_KEY", None)
