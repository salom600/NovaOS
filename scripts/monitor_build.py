#!/usr/bin/env python3
"""
NovaOS CI Build Monitor
=======================
Polls the GitHub Actions API every 30 seconds for the status of a build run
and prints progress. Exits when the run reaches a terminal state.

Usage:
    python3 monitor_build.py <run_id> <github_token>
"""
import sys
import time
import json
import urllib.request
import urllib.error

RUN_ID = sys.argv[1]
TOKEN  = sys.argv[2]
REPO   = "salom600/NovaOS"

def api(path):
    url = f"https://api.github.com/repos/{REPO}/{path}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"token {TOKEN}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "novaos-monitor",
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode())

def fmt_dur(s):
    m, s = divmod(int(s), 60)
    h, m = divmod(m, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

last_status = None
last_conclusion = None
start = time.time()
print(f"[monitor] Watching run {RUN_ID}")
print(f"[monitor] URL: https://github.com/{REPO}/actions/runs/{RUN_ID}")
print(f"[monitor] (Ctrl-C to stop polling; the build keeps running on GitHub)\n")

while True:
    try:
        run = api(f"actions/runs/{RUN_ID}")
        status = run.get("status")
        conclusion = run.get("conclusion")
        elapsed = time.time() - start

        if status != last_status or conclusion != last_conclusion:
            print(f"[{fmt_dur(elapsed)}] status={status} conclusion={conclusion}")
            last_status = status
            last_conclusion = conclusion

            if status == "in_progress":
                # Get jobs to see which step we're on
                try:
                    jobs = api(f"actions/runs/{RUN_ID}/jobs")
                    for job in jobs.get("jobs", []):
                        print(f"  -> job: {job['name']} ({job['status']}/{job.get('conclusion')})")
                        for step in job.get("steps", []):
                            mark = "✓" if step.get("conclusion") == "success" else \
                                   "✗" if step.get("conclusion") == "failure" else \
                                   "…" if step.get("status") == "in_progress" else " "
                            print(f"       {mark} {step['name']}")
                except Exception as e:
                    print(f"  (could not fetch jobs: {e})")

            if status == "completed":
                print(f"\n[monitor] BUILD {conclusion.upper()}")
                if conclusion == "success":
                    print(f"[monitor] ISO artifact should be available at:")
                    print(f"          https://github.com/{REPO}/actions/runs/{RUN_ID}")
                else:
                    print(f"[monitor] Build failed - logs at:")
                    print(f"          https://github.com/{REPO}/actions/runs/{RUN_ID}")
                sys.exit(0 if conclusion == "success" else 1)

        time.sleep(30)
    except KeyboardInterrupt:
        print("\n[monitor] Stopped by user. Build still running on GitHub.")
        sys.exit(2)
    except Exception as e:
        print(f"[monitor] error: {e}, retrying in 30s...")
        time.sleep(30)
