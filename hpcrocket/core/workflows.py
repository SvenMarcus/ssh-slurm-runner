from abc import abstractmethod
from typing import Optional

from hpcrocket.core.environmentpreparation import EnvironmentPreparation
from hpcrocket.core.filesystem import FilesystemFactory
from hpcrocket.core.launchoptions import LaunchOptions
from hpcrocket.core.slurmbatchjob import SlurmBatchJob, SlurmJobStatus
from hpcrocket.core.slurmcontroller import SlurmController

try:
    from typing import Protocol
except ImportError:
    from typing_extensions import Protocol  # type: ignore


class Workflow(Protocol):

    @abstractmethod
    def run(self, controller: SlurmController) -> int:
        pass


class LaunchWorkflow(Workflow):

    def __init__(self, filesystem_factory: FilesystemFactory, options: LaunchOptions) -> None:
        self._filesystem_factory = filesystem_factory
        self._options = options
        self._job_status: Optional[SlurmJobStatus] = None

    def run(self, controller: SlurmController) -> int:
        success = self._prepare_environment()
        if not success:
            return 1

        batch_job = controller.submit(self._options.sbatch)
        if not self._options.watch:
            return 0

        return self._wait_for_job_exit(batch_job)

    def _prepare_environment(self) -> bool:
        local_fs = self._filesystem_factory.create_local_filesystem()
        ssh_fs = self._filesystem_factory.create_ssh_filesystem()
        env_prep = EnvironmentPreparation(local_fs, ssh_fs)
        env_prep.files_to_copy(self._options.copy_files)
        try:
            env_prep.prepare()
        except (FileExistsError, FileNotFoundError):
            env_prep.rollback()
            return False

        return True

    def _wait_for_job_exit(self, batch_job: SlurmBatchJob) -> int:
        watcher = batch_job.get_watcher()
        watcher.watch(self._callback, self._options.poll_interval)
        # watcher.wait_until_done()

        if self._job_status and self._job_status.success:
            return 0

        return 1

    def _callback(self, new_status: SlurmJobStatus) -> None:
        self._job_status = new_status
