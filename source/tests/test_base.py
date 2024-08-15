import unittest

from smartfs_tools import base


class TestBase(unittest.TestCase):
    def test_SectorHeader(self):
        """
        Encode
        """
        obj = base.SectorHeader(
            logical_sector_number=0x10,
            sequence_number=0x0a23,
            crc_enable=False,
            status=base.SectorStatus(
                committed=1,
                released=0,
                crc_enable=0,
                sector_size=base.SectorSize.b512,
            )
        ).get_pack()
        self.assertEqual(obj[:4], b'\x10\x00\x23\x0a')
        self.assertEqual(obj[4], 0b10000101)
