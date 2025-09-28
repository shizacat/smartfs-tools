import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Iterator

import pytest

from smartfs_tools import script


# --- Fixtures ---

@pytest.fixture
def base_dir_with_files() -> Iterator[Path]:
    """
    Create temporary directory with files and sub directories
    Content:
        - 4 files
        - 2 sub directories

    Return
        Path to temporary directory
    """
    with TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        tmp_dir_path.joinpath("file1.txt").write_text("File 1")
        tmp_dir_path.joinpath("file2.txt").write_text("File 2")
        tmp_dir_path.joinpath("dir1").mkdir()
        tmp_dir_path.joinpath("dir1").joinpath("file3.txt").write_text("File 3")
        tmp_dir_path.joinpath("dir1").joinpath("dir2").mkdir()
        tmp_dir_path.joinpath("dir1").joinpath("dir2").joinpath(
            "file4.txt"
        ).write_text("File 4")
        yield tmp_dir_path


# --- Tests ---

def test_mode_check_with_help():
    """
    Check correctl run function mode_check_with_help
    """
    # order: entered value, expected result or exception
    correct_values = [
        ("777", "777"),
        ("000", "000"),
        ("123", "123"),
    ]
    wrong_values = [
        ("77", ValueError),
        ("7777", ValueError),
        ("abc", ValueError),
        ("78a", ValueError),
        ("877", ValueError),
    ]

    f = script.mode_check_with_help("file")
    for v in correct_values:
        assert f(v[0]) == v[1]

    for v in wrong_values:
        with pytest.raises(v[1]):
            f(v[0])


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


def test_walk_dir_find_files_01(base_dir_with_files: Path):
    """
    Check correctl run function walk_dir_find_files
    """
    r = [x for x in script.walk_dir_find_files(base_dir_with_files)]
    # check count files
    assert len(r) == 4


def test_walk_dir_find_all_dir_01(base_dir_with_files: Path):
    """
    Case 01: Sub dir correct list
    """
    r = script.walk_dir_find_all_dir(base_dir_with_files)
    assert r == ["dir1", "dir1/dir2"]


def test_main(base_dir_with_files: Path):
    """
    Check correctl run function main
    """
    with TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)
        out_file = tmp_dir_path.joinpath("out.bin")
        try:
            script.main(
                [
                    "--base-dir",
                    str(base_dir_with_files),
                    "--out",
                    str(out_file),
                    "--storage-size",
                    "1048576",
                ]
            )
            assert out_file.exists()
            assert out_file.stat().st_size == 1048576
        finally:
            if out_file.exists():
                out_file.unlink()
