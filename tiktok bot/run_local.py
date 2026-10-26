"""Test a pass without the HTTP layer. python run_local.py --video <url> --warmup"""
import argparse

from bot import worker

p = argparse.ArgumentParser()
p.add_argument("--video", action="append", default=[])
p.add_argument("--follow", action="append", default=[])
p.add_argument("--accounts", type=int, default=1)
p.add_argument("--warmup", action="store_true")
a = p.parse_args()

print(worker.run_pass(
    videos=a.video or None,
    follows=a.follow or None,
    max_accounts=a.accounts,
    warmup=a.warmup,
))
