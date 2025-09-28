import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from smartfs_tools import script


# --- Tests ---

def test_arguments():
    """
    Check correctl run function arguments
    """
    r = script.arguments(
        [
            "--base-dir",
            "test_dir",
            "--out",
            "out.bin",
            "--storage-size",
            "1048576",
        ]
    )
    assert r.base_dir == Path("test_dir")
    assert r.out == Path("out.bin")
    assert r.storage_size == 1048576
    assert r.smart_erase_block_size == 4096
    assert r.smart_sector_size == 1024
    assert r.smart_version == 1
    assert r.smart_crc == 'none'
    assert r.smart_max_len_filename == 16
    assert r.smart_number_root_dir == 0
    assert r.dir_mode == "777"
    assert r.file_mode == "666"


def test_walk_dir_find_all_dir():
    """
    Case 01: Sub dir correct list
    """
    with TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        tmp_dir_path.joinpath("dir_l1").mkdir()
        tmp_dir_path.joinpath("dir_l1").joinpath("dir_l2").mkdir()
        r = script.walk_dir_find_all_dir(tmp_dir_path)
        print(r)
