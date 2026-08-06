import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from src.links.workers.cleanup_worker import start_worker

asyncio.run(start_worker())
