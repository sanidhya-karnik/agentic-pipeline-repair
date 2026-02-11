"""Quick cleanup: remove all failed/running pipeline runs and agent actions."""
from src.config.db import execute_write

execute_write("DELETE FROM pipeline_meta.pipeline_runs WHERE status IN ('failed', 'running')")
execute_write("DELETE FROM pipeline_meta.agent_actions")
print("Done. All failed runs and agent actions cleared.")
