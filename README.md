# SmartFS tools

Python library and utilities for creating a dump of SmartsFS from a directory. The dump will be written on flash memory next.

SmartFS is a file system usage in NuttX. SmartFS stands for Sector Mapped Allocation for Really Tiny (SMART) flash.

# Links

- [SmartFS Internals](https://cwiki.apache.org/confluence/display/NUTTX/SmartFS+Internals)

# Usage

Install
```bash
pip install smartfs_tools
```

Example run:
```bash
# Veiw help
smartfs_mkdump --help

# Create dump
smartfs_mkdump \
    --base-dir ./dir_with_content \
    --out out.bin \
    --storage-size 1048576 \
    --smart-erase-block-size 4096 \
    --smart-sector-size 1024 \
    --smart-max-len-filename 16
```

# Developemnt

Run script (smartfs_mkdump):
```bash
python -m smartfs_tools.script
```
