import sys
import os
sys.path.insert(0, os.path.abspath('src/oxt/pythonpath'))
from markdown_it import MarkdownIt

md = MarkdownIt("commonmark", {"linkify": False})
# Need to enable tables since commonmark doesn't have it by default
md.enable('table')
tokens = md.parse("""
# Heading 1
This is a **bold** and *italic* paragraph.

* item 1
  * nested item

| A | B |
|---|---|
| c | d |
""")

for t in tokens:
    print(t.type, t.tag, getattr(t, 'content', ''), t.level)
