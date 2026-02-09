"""
Scheduled Monitoring: Runs health checks automatically at regular intervals.

Can run as a background thread alongside the FastAPI server,
or as a standalone process.
"""

import time
import threading
import signal
import sys
from datetime import datetime

from src.agents.monitor import create_monitor_agent, run_health_check
from src.agents.verification import create_verification_agent
from src.config.db import execute_query


class PipelineScheduler:
    """Runs pipeline health checks on a schedule."""

    def __init__(self, interval_minutes: int = 5):
        self.interval = interval_minutes * 60
        self.running = False
        self._thread = None
        self.last_check = None
        self.check_count = 0

    def _run_check(self):
        """Execute a single health check cycle."""
        self.check_count += 1
        self.last_check = datetime.now()
        print(f"[SCHEDULER] Health check #{self.check_count} at {self.last_check.strftime('%H:%M:%S')}")

        try:
            result = run_health_check()
            print(f"[SCHEDULER] Check complete. Analyzing results...")

            # Check if any critical issues were found by looking at recent agent actions
            recent_alerts = execute_query("""
                SELECT COUNT(*) as alert_count
                FROM pipeline_meta.agent_actions
                WHERE agent_name = 'monitor'
                AND action_type = 'alert'
                AND created_at > NOW() - INTERVAL '10 minutes'
            """)

            alert_count = recent_alerts[0]["alert_count"] if recent_alerts else 0
            if alert_count > 0:
                print(f"[SCHEDULER] {alert_count} new alert(s) detected!")
            else:
                print(f"[SCHEDULER] All pipelines healthy.")

        except Exception as e:
            print(f"[SCHEDULER] Error during health check: {e}")

    def _loop(self):
        """Main scheduler loop."""
        while self.running:
            self._run_check()
            # Sleep in small increments to allow clean shutdown
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)

    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            print("[SCHEDULER] Already running.")
            return

        self.running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        print(f"[SCHEDULER] Started. Running health checks every {self.interval // 60} minutes.")

    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        print("[SCHEDULER] Stopped.")

    def status(self) -> dict:
        """Get scheduler status."""
        return {
            "running": self.running,
            "interval_minutes": self.interval // 60,
            "check_count": self.check_count,
            "last_check": self.last_check.isoformat() if self.last_check else None,
        }


# Global scheduler instance
scheduler = PipelineScheduler()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run scheduled pipeline monitoring")
    parser.add_argument(
        "--interval", type=int, default=5,
        help="Health check interval in minutes (default: 5)"
    )
    args = parser.parse_args()

    sched = PipelineScheduler(interval_minutes=args.interval)

    def signal_handler(sig, frame):
        print("\nShutting down scheduler...")
        sched.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    print(f"Starting scheduled monitoring (every {args.interval} minutes)")
    print("Press Ctrl+C to stop.\n")

    sched.running = True
    sched._loop()  # Run in main thread when standalone
