from tempfile import TemporaryDirectory


def _create_temp_out_dir():
    return TemporaryDirectory(prefix="pdf2gtfs_", ignore_cleanup_errors=True)


def _remove_temp_out_dir(temp_dir: TemporaryDirectory):
    temp_dir.cleanup()
