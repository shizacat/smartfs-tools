#!/usr/bin/env python3

import argparse
from pathlib import Path
from typing import List, Optional, TypedDict

from smartfs_tools import SmartHigh, base


class Args(TypedDict):
    base_dir: str
    out: Path
    storage_size: int
    smart_erase_block_size: int
    smart_sector_size: int
    smart_version: int
    smart_crc: int
    smart_max_len_filename: int


def arguments(args_list: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create dump smartFS partition from directory"
    )
    parser.add_argument(
        "--base-dir",
        type=Path,
        required=True,
        help="The directory, from which will be created dump",
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
        help="The file name to save dump",
    )
    parser.add_argument(
        "--storage-size",
        type=int,
        required=True,
        help="Size of partition in bytes",
    )

    parser_smart = parser.add_argument_group("smart")
    parser_smart.add_argument(
        "--smart-erase-block-size",
        type=int,
        default=4096,
        help="Size of erase block on flash in bytes",
    )
    parser_smart.add_argument(
        "--smart-sector-size",
        type=int,
        help="Size of sector smartFS in bytes",
        default=1024,
        choices=base.SectorSize.to_list(),
    )
    parser_smart.add_argument(
        "--smart-version",
        type=int,
        default=1,
        choices=list(base.Version),
        help="Version of smartFS",
    )
    parser_smart.add_argument(
        "--smart-crc",
        type=str,
        default="none",
        help="CRC of smartFS",
        choices=base.CRCValue.to_list(),
    )
    parser_smart.add_argument(
        "--smart-max-len-filename",
        type=int,
        default=16,
        help="Max length of filename in smartFS",
    )
    return parser.parse_args(args_list)


def walk_dir_find_files(path: Path):
    for p in path.glob("**/*"):
        if p.is_file():
            yield p


def walk_dir_find_all_dir(path: Path) -> List[str]:
    """
    Find uniqued directories
    """
    result = set()
    for p in path.glob("**/*"):
        if p.is_dir():
            result.add(str(p.relative_to(path)))
    return list(result)


def main(args_list: Optional[List[str]] = None):
    args: Args = arguments(args_list)

    smartfs = SmartHigh(
        storage=bytearray(args.storage_size),
        formated=True,
        erase_block_size=args.smart_erase_block_size,
        smartfs_config=base.SmartFSConfig(
            sector_size=base.SectorSize.create_from_int(
                args.smart_sector_size),
            version=base.Version(args.smart_version),
            crc=base.CRCValue(args.smart_crc),
            max_len_filename=args.smart_max_len_filename,
        )
    )

    if not args.base_dir.exists():
        raise ValueError("Base dir not exists")

    for item in walk_dir_find_all_dir(args.base_dir):
        smartfs.cmd_mkdir("/" + item)

    for item in walk_dir_find_files(args.base_dir):
        with item.open("rb") as f:
            smartfs.cmd_file_create_write(
                "/" + str(item.relative_to(args.base_dir)),
                f.read()
            )

    with args.out.open("wb") as f:
        f.write(smartfs._mtd_block_layer._storage)


if __name__ == "__main__":
    main()
