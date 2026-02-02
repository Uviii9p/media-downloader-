import asyncio
from typing import Dict

class JobController:
    def __init__(self):
        self.jobs: Dict[str, asyncio.Task] = {}

    def register_job(self, job_id: str, task: asyncio.Task):
        self.jobs[job_id] = task
        task.add_done_callback(lambda t: self.jobs.pop(job_id, None))

    def cancel_job(self, job_id: str) -> bool:
        task = self.jobs.get(job_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

job_controller = JobController()
