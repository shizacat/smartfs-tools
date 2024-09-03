import unittest

from smartfs_tools.smart_high import SmartHigh
from smartfs_tools import base


class TestSmart(unittest.TestCase):

    def test__walk_sectors_in_entry_s1(self):
        """Dir entry with 1 sector"""
        # Create device
        smartfs = SmartHigh(
            storage=bytearray(10 * 1024),
            formated=True,
            erase_block_size=1024,
            smartfs_config=base.SmartFSConfig(
                sector_size=base.SectorSize.b256,
                version=base.Version.v1,
                crc=base.CRCValue.crc_disable,
            )
        )
        # Create dir
        smartfs.cmd_mkdir("/test")

        # ---
        gen = smartfs._walk_sectors_in_entry(smartfs._create_smart_entry_root())
        r = next(gen)
        self.assertIsInstance(r, base.Sector)
        with self.assertRaises(StopIteration):
            next(gen)

    def test__walk_sectors_in_entry_s2(self):
        """Dir entry with 2 sector"""
        # Create device
        smartfs = SmartHigh(
            storage=bytearray(10 * 1024),
            formated=True,
            erase_block_size=1024,
            smartfs_config=base.SmartFSConfig(
                sector_size=base.SectorSize.b256,
                version=base.Version.v1,
                crc=base.CRCValue.crc_disable,
            )
        )
        # Create dir
        for i in range(15):
            smartfs.cmd_mkdir(f"/test_{i}")

        # ---
        gen = smartfs._walk_sectors_in_entry(smartfs._create_smart_entry_root())
        r = next(gen)
        self.assertIsInstance(r, base.Sector)
        r = next(gen)
        self.assertIsInstance(r, base.Sector)
        with self.assertRaises(StopIteration):
            next(gen)
