import sys
import os
sys.path.insert(0, os.path.abspath('src/oxt/pythonpath'))

from extension.core.rich_text import RichTextInserter

class MockDoc:
    def getText(self):
        return MockText()
    def getStyleFamilies(self):
        return MockFamilies()

class MockFamilies:
    def hasByName(self, name): return False

class MockText:
    pass

inserter = RichTextInserter(MockDoc())
print(inserter.md)
