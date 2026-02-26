"""Quick script to inspect what a Hatchet @task-decorated function has."""
import os

# Set token if not already in .env
token = os.environ.get("HATCHET_CLIENT_TOKEN")
if not token:
    raise SystemExit("Set HATCHET_CLIENT_TOKEN in .env or export it")

from hatchet_sdk import Hatchet

h = Hatchet()


@h.task(name="test")
def my_task(input, ctx):
    pass


print([m for m in dir(my_task) if not m.startswith("_")])
