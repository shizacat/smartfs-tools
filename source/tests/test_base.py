import unittest

from smartfs_tools import base


class TestBase(unittest.TestCase):
    def test_SectorHeader_create(self):
        """
        Encode
        """
        # Create only from method 'create'
        obj = base.SectorHeader.create(
            version=base.Version.v1,
            logical_sector_number=0x10,
            sequence_number=0x0a23,
            crc=base.CRCValue.crc_disable,
            status=base.SectorStatus(
                committed=base.Commited.committed,
                released=base.Released.not_released,
                crc_enable=0,
                sector_size=base.SectorSize.b512,
            )
        ).get_pack()
        self.assertEqual(obj[:4], b'\x10\x00\x23\x0a')
        self.assertEqual(obj[4], 0b01000101)

    def test_SectorHeader_create_from_raw(self):
        h = base.SectorHeader.create_from_raw(b'\x10\x00\x23\x0a\x45')
        self.assertIsInstance(h, base.SectorHeaderV1)
        self.assertEqual(h.crc, base.CRCValue.crc_disable)
        self.assertEqual(h.logical_sector_number, 0x10)
        self.assertEqual(h.sequence_number, 0x0a23)

    def test_status(self):
        value_origin = 0b01001001
        # __ create
        r = base.SectorStatus.create_from_int(value_origin)
        # __ print
        print(r)
        # __check set value
        self.assertEqual(r.format_version, base.Version.v1)
        self.assertEqual(r.committed, base.Commited.committed)
        self.assertEqual(r.released, base.Released.not_released)
        self.assertEqual(r.crc_enable, 0)
        self.assertEqual(r.sector_size, base.SectorSize.b1024)
        # __ check revers value
        self.assertEqual(value_origin.to_bytes(), r.get_pack())

    def test_sector(self):
        r = base.Sector(
            storage=bytearray(100),
            is_new=True,
            header=base.SectorHeader.create(
                version=base.Version.v1,
                logical_sector_number=0x10,
                sequence_number=0x0a23,
                crc=base.CRCValue.crc_disable,
                status=base.SectorStatus(
                    committed=base.Commited.committed,
                    released=base.Released.not_released,
                    crc_enable=0,
                    sector_size=base.SectorSize.b256,
                )
            )
        )

        # test set bytes
        r.set_bytes(0, b"check")

    def test_chain_sector(self):
        r = base.ChainHeader(
            sector_type=base.SectorType.file,
            next_sector=0xffff,
            used=2,
        )
        self.assertEqual(r.get_pack(), b'\x02\xff\xff\x02\x00')

    def test_ChainHeader_from_raw(self):
        r = base.ChainHeader.create_from_raw(b"\x01\x34\x00\x05\x00")
        self.assertEqual(r.sector_type, base.SectorType.directory)
        self.assertEqual(r.next_sector, 0x34)
        self.assertEqual(r.used, 5)

    def test_SmartFSDirEntryFlags(self):
        # not set all
        r = base.SmartFSDirEntryFlags()
        self.assertEqual(r.get_pack(), b'\xff\xff')

        # set empty
        r = base.SmartFSDirEntryFlags()
        r.empty = 0
        self.assertEqual(r.get_pack(), b'\xff\x7f')

        # set active
        r = base.SmartFSDirEntryFlags()
        r.active = 0
        self.assertEqual(r.get_pack(), b'\xff\xbf')

        # set type
        r = base.SmartFSDirEntryFlags()
        r.type = base.SmartFSDirEntryType.file
        self.assertEqual(r.get_pack(), b'\xff\xdf')

        # set deleting
        r = base.SmartFSDirEntryFlags()
        r.deleting = 0
        self.assertEqual(r.get_pack(), b'\xff\xef')

    def test_SmartFSDirEntryFlags_from_raw(self):
        # set empty
        r = base.SmartFSDirEntryFlags.create_from_raw(b"\xff\x7f")
        self.assertEqual(r.empty, 0)

        # set active
        r = base.SmartFSDirEntryFlags.create_from_raw(b"\xff\xbf")
        self.assertEqual(r.active, 0)

        # set type file
        r = base.SmartFSDirEntryFlags.create_from_raw(b"\xff\xdf")
        self.assertEqual(r.type, base.SmartFSDirEntryType.file)

        # set deleting
        r = base.SmartFSDirEntryFlags.create_from_raw(b"\xff\xef")
        self.assertEqual(r.deleting, 0)

        # set mode
        r = base.SmartFSDirEntryFlags.create_from_raw(b"\x14\xFF")
        self.assertEqual(r.mode, 0x114)

    def test_SmartFSEntryHeader(self):
        r = base.SmartFSEntryHeader(
            first_sector=10,
            name="check"
        )
        p = r.get_pack(max_name_len=16)
        print(p)
        self.assertEqual(len(p), 24)

    def test_test_SmartFSEntryHeader_from_raw(self):
        r = base.SmartFSEntryHeader.create_from_raw(
            b'\xff\xff\n\x00l\xda\xc8fcheck\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00'
        )
        self.assertEqual(r.first_sector, 10)
        self.assertEqual(r.name, "check")
