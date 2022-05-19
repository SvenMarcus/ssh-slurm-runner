import functools
import os
from dataclasses import dataclass, field
from typing import Generator, List, NamedTuple, Optional

from hpcrocket.core.filesystem import Filesystem


def _join_dest_and_src(src: str, dest: str) -> str:
    return os.path.join(dest, os.path.basename(src))


class CopyInstruction(NamedTuple):
    """
    Copy instruction for a file.
    """

    source: str
    destination: str
    overwrite: bool = False

    def unglob(self, filesystem: Filesystem) -> List["CopyInstruction"]:
        if "*" in self.source:
            files = filesystem.glob(self.source)
            return [self._unglobbed_sub_instruction(file) for file in files]

        return [self]

    def _unglobbed_sub_instruction(self, file: str) -> "CopyInstruction":
        return CopyInstruction(
            file, _join_dest_and_src(file, self.destination), self.overwrite
        )


@dataclass
class CopyResult:
    copied_files: List[str]
    errors: List[Exception] = field(default_factory=list)

    @classmethod
    def empty(cls) -> "CopyResult":
        return cls([])


class _Copier:
    def __init__(
        self,
        src_fs: Filesystem,
        target_fs: Filesystem,
        *,
        abort_on_error: bool = True,
    ) -> None:
        self._src_fs = src_fs
        self._target_fs = target_fs
        self._abort_on_error = abort_on_error

    def __call__(self, copy_instruction: CopyInstruction) -> CopyResult:
        unpacked_instructions = copy_instruction.unglob(self._src_fs)
        return functools.reduce(
            self._reduce_to_copy_result, unpacked_instructions, CopyResult([])
        )

    def _reduce_to_copy_result(
        self, current_result: CopyResult, instruction: CopyInstruction
    ) -> CopyResult:
        if current_result.errors and self._abort_on_error:
            return current_result

        error = self._try_copy(instruction)

        errors = current_result.errors
        if error is None:
            current_result.copied_files.append(instruction.destination)
        else:
            errors.append(error)

        return CopyResult(current_result.copied_files, errors)

    def _try_copy(self, instruction: CopyInstruction) -> Optional[Exception]:
        try:
            self._src_fs.copy(*instruction, filesystem=self._target_fs)
        except (FileNotFoundError, FileExistsError) as err:
            return err

        return None


def progressive_copy(
    source_filesystem: Filesystem,
    target_filesystem: Filesystem,
    files: List[CopyInstruction],
    *,
    abort_on_error: bool = True,
) -> Generator[CopyResult, None, None]:
    """
    Copies the files to the target filesystem.

    Args:
        source_filesystem (Filesystem): The filesystem to copy FROM
        target_filesystem (Filesystem): The filesystem to copy TO
        files (list[CopyInstruction]): A list of CopyInstructions

    Returns:
        Generator[CopyResult]: A generator yielding individual copy results
    """
    copier = _Copier(
        source_filesystem, target_filesystem, abort_on_error=abort_on_error
    )
    for copy_instruction in files:
        tmp_result = copier(copy_instruction)
        yield tmp_result
        if tmp_result.errors and abort_on_error:
            break


def progressive_clean(
    filesystem: Filesystem, files: List[str]
) -> Generator[Exception, None, None]:
    """
    Deletes the files from the target filesystem. Files that are not found are ignored.

    Args:
        filesystem (Filesystem): The filesystem to delete files from
        files (list[str]): A list of paths to delete
        ui (Optional[UI]): A UI instance

    Returns:
        Generator[Exception]: A generator yielding exceptions that occured during cleaning
    """
    for file in files:
        try:
            filesystem.delete(file)
        except FileNotFoundError as err:
            yield err
