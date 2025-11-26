import datetime
import os
import time
from pathlib import Path

import pytest

from chronodocs.update_index import UpdateIndex


@pytest.fixture
def temp_index_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def sample_file(temp_index_dir: Path) -> Path:
    """Create a sample file with some content."""
    file_path = temp_index_dir / "test_file.md"
    file_path.write_text("Initial content")
    return file_path


def test_update_file_and_save(temp_index_dir: Path, sample_file: Path):
    """Test updating the index with a new file and saving."""
    index_path = temp_index_dir / ".update_index.json"
    index = UpdateIndex(index_path)

    index.update_file(sample_file)

    # The file should be in the index
    assert str(sample_file) in index.get_all_entries()

    initial_hash = index.get_hash(sample_file)
    assert initial_hash is not None

    index.save()
    assert index_path.is_file()

    # Now, modify the file content and check again
    sample_file.write_text("Updated content")

    index.update_file(sample_file)
    updated_hash = index.get_hash(sample_file)

    assert updated_hash is not None
    assert initial_hash != updated_hash


def test_has_changed(temp_index_dir: Path, sample_file: Path):
    """Test the has_changed method."""
    index_path = temp_index_dir / ".update_index.json"
    index = UpdateIndex(index_path)

    index.update_file(sample_file)
    index.save()

    # Initially, it has not changed
    assert not index.has_changed(sample_file)

    # After modification, it has changed
    sample_file.write_text("New content here")
    assert index.has_changed(sample_file)


def test_remove_file(temp_index_dir: Path, sample_file: Path):
    """Test removing a file from the update index."""
    index_path = temp_index_dir / ".update_index.json"
    index = UpdateIndex(index_path)

    index.update_file(sample_file)
    assert str(sample_file) in index.get_all_entries()

    index.remove_file(sample_file)
    assert str(sample_file) not in index.get_all_entries()


def test_rename_handling(temp_index_dir: Path):
    """Test that the index correctly handles file renames."""
    index_path = temp_index_dir / ".update_index.json"
    index = UpdateIndex(index_path)

    original_path = temp_index_dir / "original.md"
    original_path.write_text("some content")

    index.update_file(original_path)
    original_hash = index.get_hash(original_path)

    renamed_path = temp_index_dir / "renamed.md"
    os.rename(original_path, renamed_path)

    # After rename, tell the index about the old and new path
    index.update_file(renamed_path, old_path=original_path)

    # The old path should be gone, new one should be present
    assert str(original_path) not in index.get_all_entries()
    assert str(renamed_path) in index.get_all_entries()

    # The hash should be the same
    renamed_hash = index.get_hash(renamed_path)
    assert original_hash == renamed_hash


def test_update_file_uses_mtime(temp_index_dir: Path, sample_file: Path):
    """Test that update_file uses the file's modification time, not current time."""
    index_path = temp_index_dir / ".update_index.json"
    index = UpdateIndex(index_path)

    # Set mtime to a specific time in the past (e.g. 1 hour ago)
    past_time = time.time() - 3600
    os.utime(sample_file, (past_time, past_time))

    index.update_file(sample_file)

    # Get the stored timestamp
    entry = index.get_all_entries().get(str(sample_file))
    assert entry is not None

    stored_time_str = entry["last_content_update"]

    # Parse ISO format (handling Z which might be used in the implementation)
    if stored_time_str.endswith("Z"):
        stored_time_str = stored_time_str.replace("Z", "+00:00")

    stored_dt = datetime.datetime.fromisoformat(stored_time_str)
    stored_ts = stored_dt.timestamp()

    # Check that stored time is close to the file's mtime (allowing small jitter for float precision)
    # and significantly different from current time
    assert (
        abs(stored_ts - past_time) < 1.0
    ), f"Stored time {stored_ts} differs from mtime {past_time}"

    current_time = time.time()
    assert (
        abs(stored_ts - current_time) > 100.0
    ), "Stored time is too close to current time"
