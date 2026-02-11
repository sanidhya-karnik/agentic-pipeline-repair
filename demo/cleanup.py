"""Quick cleanup: remove all failed/running pipeline runs, agent actions, and quality failures."""
from src.config.db import execute_write

execute_write("DELETE FROM pipeline_meta.pipeline_runs WHERE status IN ('failed', 'running')")
execute_write("DELETE FROM pipeline_meta.quality_results WHERE status = 'fail'")
execute_write("DELETE FROM pipeline_meta.agent_actions")
print("Done. All failed runs, quality failures, and agent actions cleared.")
