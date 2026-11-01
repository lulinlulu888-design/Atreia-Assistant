from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'localization'))
import entry_container as container
from locale_codec import decode


class EntryContainerTests(unittest.TestCase):
    def setUp(self):
        self.keys = {container.configuration('ja-JP')[0]: bytes(range(32))}

    def test_independent_reader_checks_text_order_and_unicode(self):
        rows = {'second': '伊斯拉佩尔 {pcname}', 'first': '隐藏宝箱 😀', 'empty': '', 'ascii': '123'}
        data = container.encode(rows, self.keys, bytes(range(32)))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fixture.dat'
            path.write_bytes(data)
            result = decode(path, self.keys, 'ja-JP')
        self.assertEqual(result, rows)
        self.assertEqual(list(result), list(rows))
        self.assertEqual(container.unpack(data, self.keys)[0], bytes(range(32)))

    def test_utf16_length_counts_code_units(self):
        data = container.fstring('😀')
        self.assertEqual(struct.unpack('<i', data[:4])[0], -3)

    def test_malformed_container_is_rejected(self):
        data = container.encode({'a': '测试'}, self.keys, bytes(32))
        for invalid in (data[:-1], bytes(68), data[:20]):
            with self.assertRaises(ValueError):
                container.unpack(invalid, self.keys)

    def test_no_embedded_terminators_or_other_locales(self):
        with self.assertRaises(ValueError):
            container.encode({'a': 'x\0y'}, self.keys, bytes(32))
        with self.assertRaises(ValueError):
            container.encode({'a': '测试'}, self.keys, bytes(32), 'en-US')


if __name__ == '__main__':
    unittest.main()
