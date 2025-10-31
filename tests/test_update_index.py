import os
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
