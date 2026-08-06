import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.analytics.workers.analytics_worker import consume_url_clicked_events

asyncio.run(consume_url_clicked_events())
