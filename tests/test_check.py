import sys
import unittest


class PythonVersionTest(unittest.TestCase):
    def test_runs_on_the_declared_floor(self) -> None:
        self.assertGreaterEqual(sys.version_info[:2], (3, 15))


if __name__ == "__main__":
    unittest.main()
