import sys
import os
sys.path.insert(0, os.path.abspath('src/oxt/pythonpath'))
from extension.core.rich_text import RichTextInserter

class MockCursor:
    def getEnd(self): return 0
    def setPropertyValue(self, name, value): pass
    def gotoStart(self, b): pass
    def gotoEnd(self, b): pass

class MockText:
    def createTextCursor(self): return MockCursor()
    def insertString(self, cursor, string, b): print(f"Inserted string: {string}")
    def insertControlCharacter(self, cursor, c, b): print("Inserted newline")
    def createTextCursorByRange(self, r): return MockCursor()
    def insertTextContent(self, c, t, b): print("Inserted table")

class MockCell:
    def getText(self): return MockText()

class MockTable:
    def initialize(self, r, c): print(f"Init table {r}x{c}")
    def getCellByName(self, n): return MockCell()

class MockDoc:
    def getText(self): return MockText()
    def getStyleFamilies(self): return MockFamilies()
    def createInstance(self, name):
        if name == "com.sun.star.text.TextTable":
            return MockTable()
        return None

class MockFamilies:
    def hasByName(self, name): return False

inserter = RichTextInserter(MockDoc())
inserter._get_insert_cursor = lambda x: MockCursor()
inserter.insert_markdown("""
# Heading
Para

* list 1
* list 2

| A | B |
|---|---|
| C | D |
""")
