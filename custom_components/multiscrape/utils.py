import os


def write_file(filename, content):
    if not os.path.exists(os.path.dirname(filename)):
        try:
            os.makedirs(os.path.dirname(filename))
        except OSError as exc:  # Guard against race condition
            if exc.errno != errno.EEXIST:  # noqa: F821
                raise

    with open(filename, "w", encoding="utf8") as file:
        file.write(str(content))
