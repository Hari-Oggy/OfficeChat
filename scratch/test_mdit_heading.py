import sys, os
sys.path.insert(0, os.path.abspath('src/oxt/pythonpath'))
from markdown_it import MarkdownIt

md = MarkdownIt("commonmark", {"linkify": False})
tokens = md.parse("### Option 1")
for t in tokens:
    print(t.type, repr(t.content))
