from test.slurmoutput import DEFAULT_JOB_ID
from test.testdoubles.executor import LoggingCommandExecutorSpy


def assert_job_submitted(executor: LoggingCommandExecutorSpy, file: str) -> None:
    assert str(executor.command_log[0]) == f"sbatch {file}"


def assert_job_polled(
    executor: LoggingCommandExecutorSpy,
    jobid: str = DEFAULT_JOB_ID,
    command_index: int = 0,
) -> None:
    first_command = executor.command_log[command_index]
    assert first_command.cmd == f"sacct"
    assert first_command.args[:2] == ["-j", jobid]


def assert_job_canceled(
    executor: LoggingCommandExecutorSpy,
    jobid: str = DEFAULT_JOB_ID,
    command_index: int = 0,
) -> None:
    first_command = executor.command_log[command_index]
    assert first_command.cmd == "scancel"
    assert first_command.args == [jobid]
