"""Integration tests for file manager functionality."""

import os
import tempfile

import pytest
from homeassistant.core import HomeAssistant

from custom_components.multiscrape.file import (LoggingFileManager,
                                                create_file_manager)


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_create_file_manager_with_logging_enabled(hass: HomeAssistant):
    """Test create_file_manager creates file manager when log_response is True."""
    # Arrange
    config_name = "test_config"

    # Act
    file_manager = await create_file_manager(hass, config_name, log_response=True)

    # Assert
    assert file_manager is not None
    assert isinstance(file_manager, LoggingFileManager)
    assert "multiscrape/test_config" in file_manager.folder


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_create_file_manager_with_logging_disabled(hass: HomeAssistant):
    """Test create_file_manager returns None when log_response is False."""
    # Arrange
    config_name = "test_config"

    # Act
    file_manager = await create_file_manager(hass, config_name, log_response=False)

    # Assert
    assert file_manager is None


@pytest.mark.integration
@pytest.mark.async_test
@pytest.mark.timeout(10)
async def test_create_file_manager_slugifies_config_name(hass: HomeAssistant):
    """Test create_file_manager slugifies config name with spaces and special chars."""
    # Arrange
    config_name = "Test Config With Spaces!"

    # Act
    file_manager = await create_file_manager(hass, config_name, log_response=True)

    # Assert
    assert file_manager is not None
    assert "test_config_with_spaces" in file_manager.folder


def test_logging_file_manager_initialization():
    """Test LoggingFileManager initializes with correct folder."""
    # Arrange
    folder = "/tmp/test_folder"

    # Act
    file_manager = LoggingFileManager(folder)

    # Assert
    assert file_manager.folder == folder


def test_logging_file_manager_create_folders():
    """Test LoggingFileManager creates folders."""
    # Arrange
    with tempfile.TemporaryDirectory() as temp_dir:
        test_folder = os.path.join(temp_dir, "multiscrape", "test")
        file_manager = LoggingFileManager(test_folder)

        # Act
        file_manager.create_folders()

        # Assert
        assert os.path.exists(test_folder)
        assert os.path.isdir(test_folder)


def test_logging_file_manager_create_folders_exists_ok():
    """Test LoggingFileManager handles existing folders gracefully."""
    # Arrange
    with tempfile.TemporaryDirectory() as temp_dir:
        test_folder = os.path.join(temp_dir, "multiscrape", "test")
        file_manager = LoggingFileManager(test_folder)

        # Create folder first time
        file_manager.create_folders()

        # Act - create again (should not raise error)
        file_manager.create_folders()

        # Assert
        assert os.path.exists(test_folder)


def test_logging_file_manager_write():
    """Test LoggingFileManager writes content to file."""
    # Arrange
    with tempfile.TemporaryDirectory() as temp_dir:
        file_manager = LoggingFileManager(temp_dir)
        file_manager.create_folders()

        filename = "test_file.txt"
        content = "Test content"

        # Act
        file_manager.write(filename, content)

        # Assert
        file_path = os.path.join(temp_dir, filename)
        assert os.path.exists(file_path)
        with open(file_path, encoding="utf8") as f:
            assert f.read() == content


def test_logging_file_manager_write_with_special_content():
    """Test LoggingFileManager writes special characters correctly."""
    # Arrange
    with tempfile.TemporaryDirectory() as temp_dir:
        file_manager = LoggingFileManager(temp_dir)
        file_manager.create_folders()

        filename = "unicode_test.txt"
        content = "Special chars: \u00e9\u00e8\u00ea \u4e2d\u6587 \u0440\u0443\u0441\u0441\u043a\u0438\u0439"

        # Act
        file_manager.write(filename, content)

        # Assert
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, encoding="utf8") as f:
            assert f.read() == content


def test_logging_file_manager_write_converts_to_string():
    """Test LoggingFileManager converts non-string content to string."""
    # Arrange
    with tempfile.TemporaryDirectory() as temp_dir:
        file_manager = LoggingFileManager(temp_dir)
        file_manager.create_folders()

        filename = "dict_content.txt"
        content = {"key": "value", "number": 42}

        # Act
        file_manager.write(filename, content)

        # Assert
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, encoding="utf8") as f:
            # str(dict) includes quotes and braces
            assert "key" in f.read()


def test_logging_file_manager_empty_folder():
    """Test LoggingFileManager empties folder contents."""
    # Arrange
    with tempfile.TemporaryDirectory() as temp_dir:
        file_manager = LoggingFileManager(temp_dir)
        file_manager.create_folders()

        # Create some test files
        file_manager.write("file1.txt", "content1")
        file_manager.write("file2.txt", "content2")
        file_manager.write("file3.txt", "content3")

        # Verify files exist
        assert os.path.exists(os.path.join(temp_dir, "file1.txt"))
        assert os.path.exists(os.path.join(temp_dir, "file2.txt"))
        assert os.path.exists(os.path.join(temp_dir, "file3.txt"))

        # Act
        file_manager.empty_folder()

        # Assert
        assert not os.path.exists(os.path.join(temp_dir, "file1.txt"))
        assert not os.path.exists(os.path.join(temp_dir, "file2.txt"))
        assert not os.path.exists(os.path.join(temp_dir, "file3.txt"))
        assert os.path.exists(temp_dir)  # Folder itself should still exist


def test_logging_file_manager_empty_folder_preserves_subdirectories():
    """Test LoggingFileManager only removes files, not subdirectories."""
    # Arrange
    with tempfile.TemporaryDirectory() as temp_dir:
        file_manager = LoggingFileManager(temp_dir)
        file_manager.create_folders()

        # Create a file and a subdirectory
        file_manager.write("file.txt", "content")
        subdir = os.path.join(temp_dir, "subdir")
        os.makedirs(subdir)

        # Act
        file_manager.empty_folder()

        # Assert
        assert not os.path.exists(os.path.join(temp_dir, "file.txt"))
        assert os.path.exists(subdir)  # Subdirectory should be preserved


def test_logging_file_manager_empty_folder_handles_symlinks():
    """Test LoggingFileManager removes symlinks during empty_folder."""
    # Arrange
    with tempfile.TemporaryDirectory() as temp_dir:
        file_manager = LoggingFileManager(temp_dir)
        file_manager.create_folders()

        # Create a file and a symlink
        target_file = os.path.join(temp_dir, "target.txt")
        symlink_file = os.path.join(temp_dir, "link.txt")
        with open(target_file, "w") as f:
            f.write("target content")
        os.symlink(target_file, symlink_file)

        # Act
        file_manager.empty_folder()

        # Assert
        assert not os.path.exists(target_file)
        assert not os.path.exists(symlink_file)
