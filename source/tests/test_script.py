import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from smartfs_tools import script


class TestScript(unittest.TestCase):

    def test_walk_dir_find_all_dir(self):
        # Case 01: Sub dir correct list
        with TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            tmp_dir_path.joinpath("dir_l1").mkdir()
            tmp_dir_path.joinpath("dir_l1").joinpath("dir_l2").mkdir()
            r = script.walk_dir_find_all_dir(tmp_dir_path)
            print(r)
