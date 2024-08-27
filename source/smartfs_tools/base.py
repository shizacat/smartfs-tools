import datetime
import struct
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

import crc
from pydantic import BaseModel, Field

# Definition
# ==========


Signature = b"SMRT"

# The logical sector number of the root directory.
# SMARTFS_ROOT_DIR_SECTOR
SCTN_ROOT_DIR_SECTOR: int = 3
# First logical sector number we will use for assignment
# of requested alloc sectors.
# SMART_FIRST_ALLOC_SECTOR
SCTN_FIRST_ALLOC_SECTOR: int = 12

# Максимальный номер логического сектора, он же последний
# он же зарезервирован
LS_HIGHT_NUMBER: int = 0xffff

# Физический сектор не выделен
PS_NOT_ALLOCATED: int = 0xffff


class SectorSize(int, Enum):
    """
    The valid values for the logical sector size

    The selected size is represented using 3 bits in the logical sector
    status byte and stored on each sector.
    """
    b256 = 0b000
    b512 = 0b001
    b1024 = 0b010
    b2048 = 0b011
    b4096 = 0b100
    b8192 = 0b101
    b16384 = 0b110
    b32768 = 0b111

    @staticmethod
    def cnv_to_size(value: "SectorSize") -> int:
        """
        Convert SectorSize to size in bytes
        """
        return 2 ** (value.value + 8)

    @staticmethod
    def create_from_int(size: int) -> "SectorSize":
        """
        Convert size in bytes to SectorSize
        """
        if size == 256:
            return SectorSize.b256
        if size == 512:
            return SectorSize.b512
        if size == 1024:
            return SectorSize.b1024
        if size == 2048:
            return SectorSize.b2048
        if size == 4096:
            return SectorSize.b4096
        if size == 8192:
            return SectorSize.b8192
        if size == 16384:
            return SectorSize.b16384
        if size == 32768:
            return SectorSize.b32768
        raise ValueError("Invalid sector size")

    @classmethod
    def to_list(cls) -> List[int]:
        """
        List sizes in bytes
        """
        return [int(value[1:]) for value in cls.__members__.keys()]


class Version(int, Enum):
    """
    The valid values for the version SmartFS
    """
    v1 = 0b01
    # TODO: Implementation
    # v2 = 0b10
    # v3 = 0b11


class CRCValue(Enum):
    """
    The valid values for the CRC value
    """
    crc_disable = "none"
    crc8 = "crc8"
    crc16 = "crc16"

    @classmethod
    def to_list(cls) -> List[str]:
        """
        List CRC values
        """
        return [value.value for value in cls.__members__.values()]


class Commited(Enum):
    """
    The valid values for the commited flag
    """
    not_committed = 1
    committed = 0


class Released(Enum):
    """
    The valid values for the released flag
    """
    not_released = 1
    released = 0


class SectorType(Enum):
    directory = 1
    file = 2


# Models
# ======


@dataclass
class SectorStatus:
    """
    Sector status bit mask
    type C: uint8_t
        * Bit 7:   1 = Not committed
        *          0 = committed
        * Bit 6:   1 = Not released
        *          0 = released
        * Bit 5:   Sector CRC enable
        * Bit 4-2: Sector size on volume
        * Bit 1-0: Format version (0x1)
    """
    committed: Commited = 0
    released: Released = 0
    crc_enable: int = 0
    sector_size: SectorSize = SectorSize.b512
    format_version: Version = Version.v1

    def get_pack(self) -> bytes:
        """
        Returns the packed byte representation of the sector status
        """
        return struct.pack(
            "B",
            (self.committed.value << 7) |
            (self.released.value << 6) |
            (self.crc_enable << 5) |
            (self.sector_size.value << 2) |
            (self.format_version.value << 0)
        )

    def __repr__(self):
        return (
            f"SectorStatus("
            f"committed={self.committed}, "
            f"released={self.released}, "
            f"crc_enable={self.crc_enable}, "
            f"sector_size={self.sector_size}, "
            f"format_version={self.format_version}"
            f")"
        )

    @staticmethod
    def create_from_int(value: int) -> "SectorStatus":
        """
        Create a new instance of the sector status from the byte value
        """
        return SectorStatus(
            committed=Commited((value >> 7) & 0x1),
            released=Released((value >> 6) & 0x1),
            crc_enable=(value >> 5) & 0x1,
            sector_size=SectorSize((value >> 2) & 0x7),
            format_version=Version((value >> 0) & 0x3),
        )


class SectorHeader:
    """
    Base class for sector header
    """

    def __init__(
        self,
        sh_size: int,
    ):
        """
        Args:
            sh_size: int - The size of the sector header in bytes
        """
        self._sh_size = sh_size
        self.logical_sector_number: int
        self.sequence_number: int
        self.status: SectorStatus
        self.crc_value: int = 0
        self.crc: CRCValue = CRCValue.crc_disable

    @classmethod
    def create(
        cls, version: Version, *args, **kwargs
    ) -> "SectorHeader":
        """
        Create a new instance of the sector header
        """
        if version == Version.v1:
            return SectorHeaderV1(*args, **kwargs)
        raise ValueError("Invalid version")

    @classmethod
    def create_from_raw(cls, value: bytes) -> "SectorHeader":
        """
        Создает заголовок из строки байтов
        """
        if len(value) != 5:
            raise ValueError("Invalid sector header size")
        status = SectorStatus.create_from_int(int(value[4]))
        if status.format_version == Version.v1:
            return SectorHeaderV1.create_from_bytes(
                value=value, status=status)
        raise ValueError("Invalid version")

    @property
    def size(self) -> int:
        """
        Return the size of the sector header, bytes
        """
        return self._sh_size

    def get_pack(self) -> bytes:
        raise NotImplementedError()


class SectorHeaderV1(SectorHeader):
    """
    Sector header, size 5 bytes, for SmartFS Version 1
    Support only crc8

    uint8_t               logicalsector[2]; /* The logical sector number */
    uint8_t               seq;              /* Incrementing sequence number */
    uint8_t               crc8;             /* CRC-8 or seq number MSB */
    uint8_t               status;           /* Status of this sector:
    """

    def __init__(
        self,
        logical_sector_number: int,
        sequence_number: int,
        status: SectorStatus,
        crc_value: int = 0,
        crc: CRCValue = CRCValue.crc_disable
    ):
        super().__init__(sh_size=5)
        self.logical_sector_number = logical_sector_number
        self.sequence_number = sequence_number
        self.status = status
        self.crc_value = crc_value
        self.crc = crc

    def get_pack(self) -> bytes:
        """
        Return the packed byte representation of the sector header
        """
        if self.crc == CRCValue.crc_disable:
            return struct.pack(
                "<HBB",
                self.logical_sector_number,
                self.sequence_number & 0x00FF,
                self.sequence_number >> 8,
            ) + self.status.get_pack()

        if self.crc == CRCValue.crc8:
            return struct.pack(
                "<HBB",
                self.logical_sector_number,
                self.sequence_number & 0x00FF,
                self.crc_value,
            ) + self.status.get_pack()

        raise ValueError("CRC value is not supported")

    @classmethod
    def create_from_bytes(
        cls, value: bytes, status: Optional[SectorStatus]
    ) -> "SectorHeaderV1":
        if status is None:
            status = SectorStatus.create_from_int(value[4])

        seq_number = int(value[2])

        crc_value = 0
        crc = CRCValue.crc_disable
        if status.crc_enable == 1:
            crc_value = int(value[3])
            crc = CRCValue.crc8
        else:
            seq_number += (int(value[3]) << 8)

        status.crc_enable
        return SectorHeaderV1(
            logical_sector_number=int.from_bytes(value[0:2], "little"),
            sequence_number=seq_number,
            status=status,
            crc_value=crc_value,
            crc=crc,
        )


class ChainHeader(BaseModel):
    """
    Chain header, CH, 5 bytes
    If next_sector == EraseState (0xff) then it last sector in the chain
    """
    sector_type: SectorType = Field(
        ..., description="Type of sector entry (file or dir) ")
    next_sector: int = Field(
        ..., description="Next logical sector in the chain")
    used: int = Field(..., description="Number of bytes used in this sector")

    def get_pack(self) -> bytes:
        """
        Return the packed byte representation
        """
        return struct.pack(
            "<BHH",
            self.sector_type.value,
            self.next_sector,
            self.used,
        )

    @classmethod
    def get_size(cls) -> int:
        return 5

    @classmethod
    def create_from_raw(cls, value: bytes) -> "ChainHeader":
        """
        Создает заголовок из строки байтов
        """
        if len(value) != cls.get_size():
            raise ValueError("Invalid chain header size")
        return ChainHeader(
            sector_type=SectorType(value[0]),
            next_sector=int.from_bytes(value[1:3], "little"),
            used=int.from_bytes(value[3:5], "little"),
        )


class Sector:
    """
    Сектор
    """

    def __init__(
        self,
        storage: bytearray,
        header: Optional[SectorHeader] = None,
        is_new: bool = False,
        fill_value: bytes = b"\xFF",
    ):
        """
        Args:
            is_new - будет заполнено новыми структурами
                иначе будет вычитывать и парсить
        """
        self._storage = storage
        self._fill_value = fill_value

        if is_new:
            if header is None:
                raise ValueError("Header is required")
            self._header = header
            self._fill()
            self._header.crc_value = self._calc_crc()
            self._save_header()
        else:
            self._header = SectorHeader.create_from_raw(self._storage[0:5])

    def set_bytes(self, pfrom: int, value: bytes):
        """
        Записывает в нужное место данные.
        Сразу рассчитывается crc если это нужно

        Args:
            pfrom - позиция считается после заголовка
        """
        start_position = self._header.size + pfrom
        end_position = self._header.size + pfrom + len(value)
        if end_position > len(self._storage):
            raise ValueError(
                f"The end position ({end_position}) is greater than the "
                f"length of the buffer ({len(self._storage)})"
            )
        self._storage[start_position:end_position] = value

        self._header.crc_value = self._calc_crc()
        self._save_header()

    def _fill(self):
        """
        Заполняет пустое место в секторе
        """
        self._storage[0:1] = b"a"
        self._storage[self._header.size:] = self._fill_value * (
            len(self._storage) - self._header.size
        )

    def _save_header(self):
        self._storage[0:self._header.size] = self._header.get_pack()

    def _calc_crc(self) -> int:
        """
        Return CRC value
        TODO: lenght 8, 16, 32
        """
        calc = None

        if self._header.crc == CRCValue.crc_disable:
            return
        if self._header.crc == CRCValue.crc8:
            calc = crc.Calculator(crc.Crc8.CCITT)

        if calc is None:
            raise ValueError("CRC value is not supported")

        # Calculation
        buffer: bytes = b""
        # __ Calculate CRC on data region of the sector
        buffer += self._storage[self._header.size:]
        # __ Add logical sector number and seq to the CRC calculation, 3 byte
        buffer += self._header.get_pack()[:3]
        # __ Add status to the CRC calculation, 1 byte
        buffer += self._header.status.get_pack()
        return calc.checksum(buffer)

    def get_size(self) -> int:
        """
        Возвращает размер доступного места в секторе
        """
        return len(self._storage) - self._header.size

    def read_object(self, class_name, offset: int = 0, size: int = 0):
        """
        Читает объект по заданному адрсу

        Args:
            offset, смещенеи относительно SH
        """
        b_start = self._header.size + offset
        b_end = b_start + size
        if b_end > len(self._storage):
            raise ValueError(
                f"The end position ({b_end}) is greater than the "
                f"size of the sector ({len(self._storage)})"
            )
        return class_name.create_from_raw(self._storage[b_start:b_end])

    def borders_is_big(self, offset: int, size: int) -> bool:
        """
        Проверяет, что начало и конец данных не выходят за границы сектора

        Return
            True - если выходит за границы
        """
        b_start = self._header.size + offset
        b_end = b_start + size
        if b_start > len(self._storage):
            return True
        if b_end > len(self._storage):
            return True
        return False

    def get_next_sector_number(self) -> Optional[int]:
        """
        Reads chain header and return next sector number (logical)
        in chain if it exist
        """
        b_start = self._header.size
        b_end = b_start + ChainHeader.get_size()
        ch = ChainHeader.create_from_raw(self._storage[b_start:b_end])
        if ch.next_sector == -1:  # End chain
            return None
        return ch.next_sector


class SmartFSConfig(BaseModel):
    """
    Настройки виртуального устрояйства со SmartFS
    """
    sector_size: SectorSize = Field(
        SectorSize.b512, description="Размер сектрота")
    version: Version = Field(Version.v1, description="Версия SmartFS")
    crc: CRCValue = Field(
        CRCValue.crc_disable, description="CRC alhorithm, or disable")
    max_len_filename: int = Field(
        16, description="Максимальная длинна имени файла")
    number_root_dir: int = Field(
        0,
        description=(
            "Количество корневых директорий, "
            "if 0 - only one root directory"
        )
    )


class SmartStruct(BaseModel):
    """
    Расчетные данные для работы SmartFS

    uint16_t              neraseblocks;     /* Number of erase blocks or sub-sectors */
    uint16_t              lastallocblock;   /* Last  block we allocated a sector from */
    uint16_t              freesectors;      /* Total number of free sectors */
    uint16_t              releasesectors;   /* Total number of released sectors */
    uint16_t              mtdblkspersector; /* Number of MTD blocks per SMART Sector */
    uint16_t              sectorsperblk;    /* Number of sectors per erase block */
    uint16_t              sectorsize;       /* Sector size on device */
    uint16_t              totalsectors;     /* Total number of sectors on device */
    uint32_t              erasesize;        /* Size of an erase block */
    FAR uint8_t          *releasecount;     /* Count of released sectors per erase block */
    FAR uint8_t          *freecount;        /* Count of free sectors per erase block */
    FAR char             *rwbuffer;         /* Our sector read/write buffer */
    char                  partname[SMART_PARTNAME_SIZE];
    uint8_t               formatversion;    /* Format version on the device */
    uint8_t               formatstatus;     /* Indicates the status of the device format */
    uint8_t               namesize;         /* Length of filenames on this device */
    uint8_t               debuglevel;       /* Debug reporting level */
    uint8_t               availsectperblk;  /* Number of usable sectors per erase block */
    FAR uint16_t         *smap;             /* Virtual to physical sector map */
    """  # noqa: E501
    neraseblocks: int = Field(
        ..., description="Number of erase blocks or sub-sectors")
    sectorsperblk: int = Field(
        ..., description="Number of sectors per erase block")
    availsectperblk: int = Field(
        ..., description="Number of usable sectors per erase block")
    totalsectors: int = Field(
        ..., description="Total number of sectors on device")
    # -----------------
    # Change in runtime
    # -----------------
    freesectors: int = Field(
        0, description="Total number of free sectors")
    # PS_NOT_ALLOCATED - is empty logical sector.
    smap: Dict[int, int] = Field(
        default_factory=dict, description="Logical to physical sector map")
    lastallocblock: int = Field(
        0, description="Last block (erase block) we allocated a sector from")
    # eb:sector -> 0 - allocated; 1 - free
    free_sector_map: List[List[bool]] = Field(
        default_factory=list,
        description="Count of free sectors per erase block")


class SmartFSEntry(BaseModel):
    """
    This is an in-memory representation of the SMART inode as extracted from
    FLASH and with additional state information.

    struct smartfs_entry_s
    {
    uint16_t          firstsector;  /* Sector number of the name */
    uint16_t          dsector;      /* Sector number of the directory entry */
    uint16_t          doffset;      /* Offset of the directory entry */
    uint16_t          dfirst;       /* 1st sector number of the directory entry
    uint16_t          flags;        /* Flags, including mode */
    FAR char          *name;        /* inode name */
    uint32_t          utc;          /* Time stamp */
    uint32_t          datlen;       /* Length of inode data */
    };
    """
    # TODO: rename
    # First sector of directory
    first_sector: int = Field(
        ..., description="Logical sector number of the name")
    # Sector wehre stored directory entry
    dir_sector: int = Field(
        ..., description="Logical sector number of the directory entry")
    dir_offset: int = Field(
        ..., description="Offset of the directory entry, from SH")
    name: str = Field(..., description="Inode name")


class SmartFSDirEntryType(int, Enum):
    """
    #define SMARTFS_DIRENT_TYPE_DIR   0x2000
    #define SMARTFS_DIRENT_TYPE_FILE  0x0000
    """
    file = 0
    dir = 1


class SmartFSDirEntryFlags(BaseModel):
    """
    /* Directory entry flag definitions */
    0 - set; 1 - unset

    #define SMARTFS_DIRENT_EMPTY      0x8000  /* Set to non-erase state when entry used */
    #define SMARTFS_DIRENT_ACTIVE     0x4000  /* Set to erase state when entry is active */
    #define SMARTFS_DIRENT_TYPE       0x2000  /* Indicates the type of entry (file/dir) */
    #define SMARTFS_DIRENT_DELETING   0x1000  /* Directory entry is being deleted */

    #define SMARTFS_DIRENT_RESERVED   0x0E00  /* Reserved bits */
    #define SMARTFS_DIRENT_MODE       0x01FF  /* Mode the file was created with */

    #define SMARTFS_BFLAG_DIRTY       0x01    /* Set if data changed in the sector */
    #define SMARTFS_BFLAG_NEWALLOC    0x02    /* Set if sector not written since alloc */
    """  # noqa: E501
    empty: int = Field(
        1, description="Set to non-erase state when entry used")
    active: int = Field(
        1, description="Set to erase state when entry is active")
    type: SmartFSDirEntryType = Field(
        SmartFSDirEntryType.dir,
        description="Indicates the type of entry (file - 0/dir - 1)")
    deleting: int = Field(
        1, description="Directory entry is being deleted")
    mode: int = Field(
        0x01FF, description="Mode the file was created with")

    def get_pack(self) -> bytes:
        """
        Return a 2-byte packed
        """
        return struct.pack(
            "<H",
            self.empty << 15 |
            self.active << 14 |
            self.type.value << 13 |
            self.deleting << 12 |
            0b111 << 9 |
            self.mode
        )

    @classmethod
    def create_from_raw(self, values: bytes) -> "SmartFSDirEntryFlags":
        """
        Order bytes: little endian (LSB first)
        """
        return SmartFSDirEntryFlags(
            empty=(values[1] & 0x80) >> 7,
            active=(values[1] & 0x40) >> 6,
            type=SmartFSDirEntryType((values[1] & 0x20) >> 5),
            deleting=(values[1] & 0x10) >> 4,
            mode=(values[0] + (values[1] << 8)) & 0x01FF
        )

    @property
    def size(self) -> int:
        """bytes"""
        return 2


class SmartFSEntryHeader(BaseModel):
    """
    This is an on-device representation of the SMART inode as it exists on
    the FLASH.

    struct smartfs_entry_header_s
    {
    uint16_t          flags;        /* Flags, including permissions:
                                    *  15:   Empty entry
                                    *  14:   Active entry
                                    *  12-0: Permissions bits */
    int16_t           firstsector;  /* Sector number of the name */
    uint32_t          utc;          /* Time stamp */
    char              name[0];      /* inode name */
    };
    """
    flags: SmartFSDirEntryFlags = Field(
        SmartFSDirEntryFlags(), description="Flags, including permissions")
    first_sector: int = Field(
        ..., description="Logical sector number where stored entity")
    utc: datetime.datetime = Field(
        datetime.datetime.now(tz=datetime.timezone.utc),
        description="Time stamp")
    name: str = Field(
        ..., description="Inode name")

    def get_pack(self, max_name_len: int) -> bytes:
        """
        Return a packed header

        Args
            max_name_len: Length of the name, how bytes will be used for name
        """
        if len(self.name) > max_name_len:
            raise ValueError(
                f"Name {self.name} is longer than {max_name_len} bytes")
        name = (
            self.name.encode("ascii") +
            b"\x00" * (max_name_len - len(self.name))
        )
        return self.flags.get_pack() + struct.pack(
            "<h", self.first_sector) + struct.pack(
            "<I", int(self.utc.timestamp())) + name

    @classmethod
    def create_from_raw(cls, value: bytes) -> "SmartFSEntryHeader":
        """
        Order bytes: little endian (LSB first)
        Full length dependency from max_len_filename
        """
        # Skip if name start from 0xff
        name = ""
        if value[8] != 0xff:
            name = bytes(value[8:]).decode("ascii").rstrip("\x00")

        return SmartFSEntryHeader(
            flags=SmartFSDirEntryFlags.create_from_raw(value[:2]),
            first_sector=struct.unpack("<h", value[2:4])[0],
            utc=datetime.datetime.fromtimestamp(
                struct.unpack("<I", value[4:8])[0],
                datetime.timezone.utc
            ),
            name=name
        )

    @classmethod
    def get_size(self, max_len_filename: int) -> int:
        """
        Return the size of the header in bytes with
        add max len filename
        """
        return 2 + 2 + 4 + max_len_filename
