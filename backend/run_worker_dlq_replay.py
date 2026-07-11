import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.workers.dlq_replay_worker import consume_dlq_replay

asyncio.run(consume_dlq_replay())
