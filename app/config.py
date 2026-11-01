"""Block 1 configuration: environment only, no secrets, no network.

Defaults are zero-config local paths. Later blocks read cloud
credentials from the environment; Block 1 never reads or uses them.
"""

import os

DB_PATH = os.environ.get("HIVE_MIND_DB_PATH", "data/hive-mind.db")
VAULT_DIR = os.environ.get("HIVE_MIND_VAULT_DIR", "vault")
EMBED_DIM = int(os.environ.get("EMBED_DIM", "768"))

VERSION = "0.1.0-block1"
SERVER_NAME = "hive-mind-mcp"
