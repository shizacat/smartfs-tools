from typing import Optional

from smartfs_tools import base

from .base import (
    SCTN_ROOT_DIR_SECTOR,
    ChainHeader,
    Commited,
    CRCValue,
    Released,
    Sector,
    SectorHeader,
    SectorSize,
    SectorStatus,
    SectorType,
    Signature,
)


class MTDBlockLayer:
    """
    Класс для работы с виртуальным устройством с файловой
    системой SmartFS.

    This layer manages all low-level FLASH access operations
    including:
        - sector allocations,
        - logical to physical sector mapping,
        - erase operations,
        - etc ...
    """

    def __init__(
        self,
        erase_block_size: int,
        storage: bytearray,
        fill_value: bytes = b"\xFF",
        smartfs_config: base.SmartFSConfig = base.SmartFSConfig(),
        formated: bool = False,
    ):
        """
        Args:
            device_size: int - в байтах, размер устройсва
            erase_block_size - в байтах, размер erase block,
                esp32s3 spi flash - 4096
            number_root_dir - Record the number of root directory entries
                we have, if 1 - without multi directory
        """
        self._storage: bytearray = storage
        self._erase_block_size = erase_block_size
        self._fill_value = fill_value
        self._smartfs_config = smartfs_config

        # Calculation
        self._sector_size_byte = SectorSize.cnv_to_size(
            self._smartfs_config.sector_size)
        self._device_size = len(self._storage)

        self._initialize()

        if formated:
            # Fill default
            self._storage[:] = self._fill_value * self._device_size
            self._llformat()
            self._fs_media_write()

            # TODO: подумать, может убрать в другое место
            self._smart_struct.free_sector_map[0][0] = 0
            # set allocated 0 sector
        else:
            pass
            # TODO: scan device

    def _initialize(self):
        """
        name: smart_initialize
        """
        neraseblocks = self._device_size // self._erase_block_size
        sectorsperblk = self._erase_block_size // self._sector_size_byte
        totalsectors = neraseblocks * sectorsperblk

        self._smart_struct = base.SmartStruct(
            neraseblocks=neraseblocks,
            sectorsperblk=sectorsperblk,
            availsectperblk=sectorsperblk,
            totalsectors=totalsectors,
            # Runtime
            freesectors=totalsectors,
            smap={x: base.PS_NOT_ALLOCATED for x in range(totalsectors)},
            lastallocblock=0,
            free_sector_map=[[1] * sectorsperblk] * neraseblocks,
        )

        # Total number of sectors on device
        if self._smart_struct.totalsectors > 65536:
            raise ValueError(
                f"Invalid SMART sector count {self._smart_struct.totalsectors}"
            )
        if self._smart_struct.totalsectors == 65536:
            # Special case.  We allow 65536 sectors and simply waste 2 sectors
            # to allow a smaller sector size with almost maximum flash usage.
            self._smart_struct.totalsectors -= 2

    def _llformat(self):
        """
        Low level format
        name: _smart_llformat

        - Add 'Format header' (FH)
        """
        # Construct a logical sector zero
        # SH
        self._allocsector(requested=0, physical_sector=0)

        sector = self._phy_sector_get(phy_sector_number=0)

        # FH
        # __ Add the format signature to the sector
        sector.set_bytes(pfrom=0, value=Signature)
        # __ Add version
        sector.set_bytes(
            pfrom=len(Signature),
            value=self._smartfs_config.version.value.to_bytes(
                length=1, byteorder="little"
            )
        )
        # __ Add max length of file
        sector.set_bytes(
            pfrom=len(Signature) + 1,
            value=self._smartfs_config.max_len_filename.to_bytes(
                length=1, byteorder="little"
            ),
        )
        # __ Add root directory entries
        sector.set_bytes(
            pfrom=len(Signature) + 2,
            value=self._smartfs_config.number_root_dir.to_bytes(
                length=1, byteorder="little"
            ),
        )

    def _allocsector(
        self,
        requested: int = base.LS_HIGHT_NUMBER,
        physical_sector: Optional[int] = None,
    ) -> int:
        """
        Allocates a new logical sector. If an argument is given,
        then it tries to allocate the specified sector number.
        name: smart_allocsector

        Return
            logical sector number
        """
        logsector = base.LS_HIGHT_NUMBER
        # physicalsector

        # Validate that we have enough sectors available to perform
        # an allocation.
        if self._smart_struct.freesectors < self._smart_struct.sectorsperblk + 4:  # noqa: E501
            raise ValueError("Not enough free sectors")

        # Check logical sector is free
        if requested >= 0 and requested < self._smart_struct.totalsectors:
            if self._smart_struct.smap.get(requested) != base.PS_NOT_ALLOCATED:
                raise ValueError(f"Sector {requested} is already allocated")
            logsector = requested

        # Check if we need to scan for an available logical sector
        if requested == base.LS_HIGHT_NUMBER:
            for x in range(
                base.SCTN_FIRST_ALLOC_SECTOR, self._smart_struct.totalsectors
            ):
                if self._smart_struct.smap[x] == base.PS_NOT_ALLOCATED:
                    logsector = x
                    break

        # Test for an error allocating a sector
        if logsector == base.LS_HIGHT_NUMBER:
            raise ValueError("No available logical sector")

        # Find a free physical sector
        if physical_sector is None:
            physical_sector = self._findfreephyssector()

        if physical_sector == base.PS_NOT_ALLOCATED:
            raise ValueError("No available physical sector")

        # Write the logical sector to the flash.
        # We will fill it in with data late.
        # write only header (FS), analog: smart_write_alloc_sector
        self._phy_sector_create(
            phy_sector_number=physical_sector,
            logical_sector_number=logsector,
            sequence_number=0)

        # Update struct
        self._smart_struct.smap[logsector] = physical_sector
        self._smart_struct.freesectors -= 1

        return logsector

    def _findfreephyssector(self) -> int:
        """
        Find free physical sector
        """
        physical_sector = base.PS_NOT_ALLOCATED

        # Reset counter
        self._smart_struct.lastallocblock += 1
        if (
            self._smart_struct.lastallocblock >=
            self._smart_struct.neraseblocks
        ):
            self._smart_struct.lastallocblock = 0

        block = self._smart_struct.lastallocblock
        for eb, sectors in enumerate(self._smart_struct.free_sector_map):
            block_count_free_sector = sum(
                self._smart_struct.free_sector_map[block])
            # Block have all free secotors
            if block_count_free_sector == self._smart_struct.sectorsperblk:
                break
            # Not free sectors
            if sum(sectors) == 0:
                continue
            if sum(sectors) > block_count_free_sector:
                block = eb

        if sum(self._smart_struct.free_sector_map[block]) == 0:
            raise ValueError("No available physical sector")

        for i, sector in enumerate(self._smart_struct.free_sector_map[block]):
            if sector == 1:
                physical_sector = block * self._smart_struct.sectorsperblk + i
                self._smart_struct.free_sector_map[block][i] = 0
                self._smart_struct.lastallocblock = block
                break

        # Now check on the physical media
        # TODO

        return physical_sector

    def _phy_sector_create(
        self,
        phy_sector_number: int,
        logical_sector_number: int = 0,
        sequence_number: int = 0,
    ) -> Sector:
        """
        Создает новый физический сектор.
          - Записывает Sector Header в сектор

        Не проверяет существование старого
        """
        print("Create phy sector number: ", phy_sector_number)
        # Get border
        b_start = phy_sector_number * self._sector_size_byte
        b_end = b_start + self._sector_size_byte

        # TODO: может создавать в __init__
        view = memoryview(self._storage)
        return Sector(
            is_new=True,
            fill_value=self._fill_value,
            storage=view[b_start:b_end],
            header=SectorHeader.create(
                version=self._smartfs_config.version,
                logical_sector_number=logical_sector_number,
                sequence_number=sequence_number,
                crc=self._smartfs_config.crc,
                status=SectorStatus(
                    committed=Commited.committed,
                    released=Released.not_released,
                    crc_enable=0 if self._smartfs_config.crc == CRCValue.crc_disable else 1,  # noqa: E501
                    sector_size=self._smartfs_config.sector_size,
                    format_version=self._smartfs_config.version,
                )
            )
        )

    def _phy_sector_get(self, phy_sector_number: int) -> Sector:
        """
        Только получает, читает сектор
        """
        # Checks
        if (
            phy_sector_number > 65535 or
            phy_sector_number == base.PS_NOT_ALLOCATED
        ):
            raise ValueError("Invalid physical sector number")

        # Get border
        b_start = phy_sector_number * self._sector_size_byte
        b_end = b_start + self._sector_size_byte

        # TODO: может создавать в __init__
        view = memoryview(self._storage)
        return Sector(is_new=False, storage=view[b_start:b_end])

    def _log_sector_get(self, log_sector: int) -> Sector:
        """
        Возвращает физический сектор соответсвующий логическому
        """
        return self._phy_sector_get(self._smart_struct.smap[log_sector])

    def _fs_media_write(self):
        """
        Write the filesystem to media.
        Loop for each root dir entry and allocate the reserved Root Dir Entry,
        then write a blank root dir for it.

        'Chain Header' (CH)
        """
        sector_number = SCTN_ROOT_DIR_SECTOR
        for i in range(self._smartfs_config.number_root_dir + 1):
            self._allocsector(requested=sector_number)
            sector = self._log_sector_get(sector_number)
            ch = ChainHeader(
                sector_type=SectorType.directory,
                next_sector=0xffff,
                used=0xffff,
            )
            sector.set_bytes(pfrom=0, value=ch.get_pack())

            # set next dir sector
            sector_number += 1

    @property
    def dump(self) -> bytes:
        """Возвращает содержимое виртуального диска"""
        return bytes(self._storage)
