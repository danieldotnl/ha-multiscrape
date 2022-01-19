import os


class LoggingFileManager:
    def __init__(self, folder):
        self.folder = folder

    def create_folders(self):
        if not os.path.exists(os.path.dirname(self.folder)):
            try:
                os.makedirs(os.path.dirname(self.folder))
            except OSError as exc:  # Guard against race condition
                if exc.errno != errno.EEXIST:  # noqa: F821
                    raise

    def empty_folder(self):
        for filename in os.listdir(self.folder):
            file_path = os.path.join(self.folder, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)

    def write(self, filename, content):
        path = os.path.join(self.folder, filename)
        with open(path, "w", encoding="utf8") as file:
            file.write(str(content))
