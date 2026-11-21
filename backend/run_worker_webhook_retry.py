import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.webhooks.workers.webhook_retry_worker import start_worker

asyncio.run(start_worker())
