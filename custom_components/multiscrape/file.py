"""LoggingFileManager for file utilities."""
import os


class LoggingFileManager:
    """LoggingFileManager for handling logging files."""

    def __init__(self, folder):
        """Initialize the LoggingFileManager."""
        self.folder = folder

    def create_folders(self):
        """Create folders for the logging files."""
        if not os.path.exists(os.path.dirname(self.folder)):
            try:
                os.makedirs(os.path.dirname(self.folder))
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:  # noqa: F821
                    raise

    def empty_folder(self):
        """Empty the logging folders (typically called before a new run)."""
        for filename in os.listdir(self.folder):
            file_path = os.path.join(self.folder, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)

    def write(self, filename, content):
        """Write the logging content to a file."""
        path = os.path.join(self.folder, filename)
        with open(path, "w", encoding="utf8") as file:
            file.write(str(content))
