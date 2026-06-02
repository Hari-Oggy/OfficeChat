import sys
import os
sys.path.insert(0, os.path.abspath('src/oxt/pythonpath'))
from markdown_it import MarkdownIt

md = MarkdownIt("commonmark", {"linkify": False})
md.enable('table')
tokens = md.parse("This is a **bold** and *italic* and `code` span")

for t in tokens:
    if t.type == 'inline':
        for child in t.children:
            print("  ", child.type, child.tag, getattr(child, 'content', ''))
