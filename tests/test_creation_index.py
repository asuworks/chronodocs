import os
import time
from pathlib import Path

import pytest

from chronodocs.creation_index import CreationIndex


@pytest.fixture
def temp_index_dir(tmp_path: Path) -> Path:
    # A temporary directory for index files
    return tmp_path


@pytest.fixture
def sample_files(temp_index_dir: Path) -> list[Path]:
    """Create some sample files to be indexed."""
    files = [
        temp_index_dir / "file1.md",
        temp_index_dir / "file2.txt",
    ]
    for f in files:
        f.touch()
        # Sleep to ensure distinct ctimes, although on modern filesystems it's not always guaranteed.
        time.sleep(0.01)
    return files


def test_add_file_and_save(temp_index_dir: Path, sample_files: list[Path]):
    """Test adding files to the index and saving it."""
    index_path = temp_index_dir / ".creation_index.json"
    index = CreationIndex(index_path)

    for f in sample_files:
        index.add_file(f)

    # All files should be in the internal entries dict
    assert len(index.get_all_entries()) == len(sample_files)

    index.save()

    # The index file should now exist
    assert index_path.is_file()

    # Load it again to verify content
    new_index = CreationIndex(index_path)
    assert len(new_index.get_all_entries()) == len(sample_files)

    file1_key = new_index.get_file_key(sample_files[0])
    assert file1_key in new_index.get_all_entries()
    assert new_index.get_all_entries()[file1_key]["filename"] == "file1.md"


def test_remove_file(temp_index_dir: Path, sample_files: list[Path]):
    """Test removing a file from the index."""
    index_path = temp_index_dir / ".creation_index.json"
    index = CreationIndex(index_path)

    for f in sample_files:
        index.add_file(f)

    assert len(index.get_all_entries()) == 2

    index.remove_file(sample_files[0])

    assert len(index.get_all_entries()) == 1

    file1_key = index.get_file_key(sample_files[0])
    assert file1_key not in index.get_all_entries()


def test_get_ctime_for_file(temp_index_dir: Path, sample_files: list[Path]):
    """Test retrieving the recorded creation time."""
    index_path = temp_index_dir / ".creation_index.json"
    index = CreationIndex(index_path)

    start_time = time.time()
    index.add_file(sample_files[0])
    end_time = time.time()

    ctime = index.get_ctime_for_file(sample_files[0])
    assert ctime is not None
    assert start_time <= ctime <= end_time


def test_file_key_stability_on_rename(temp_index_dir: Path):
    """On POSIX systems, the key should be stable even if a file is renamed."""
    if os.name != "posix":
        pytest.skip("Inode/device keying is only supported on POSIX.")

    index_path = temp_index_dir / ".creation_index.json"
    index = CreationIndex(index_path)

    original_path = temp_index_dir / "original.md"
    original_path.touch()

    original_key = index.get_file_key(original_path)

    renamed_path = temp_index_dir / "renamed.md"
    os.rename(original_path, renamed_path)

    renamed_key = index.get_file_key(renamed_path)

    assert original_key == renamed_key
