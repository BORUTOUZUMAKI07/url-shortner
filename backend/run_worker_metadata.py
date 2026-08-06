import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.webhooks.workers.metadata_worker import consume_url_created

asyncio.run(consume_url_created())
