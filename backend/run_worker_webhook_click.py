import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.webhooks.workers.webhook_click_consumer import consume_url_clicked_webhooks

asyncio.run(consume_url_clicked_webhooks())
