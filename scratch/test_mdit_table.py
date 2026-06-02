import sys, os
sys.path.insert(0, os.path.abspath('src/oxt/pythonpath'))
from markdown_it import MarkdownIt

md = MarkdownIt("commonmark", {"linkify": False})
md.enable('table')
tokens = md.parse("""| A | B |\n|---|---|\n| C | D |""")
for i, t in enumerate(tokens):
    if t.type in ('th_open', 'td_open'):
        print(f"{t.type} at {i}, next is {tokens[i+1].type}")
