import unittest

from smartfs_tools import smart


class TestSmart(unittest.TestCase):

    def test_create_default(self):
        sm_dev = smart.SmartVDevice()
