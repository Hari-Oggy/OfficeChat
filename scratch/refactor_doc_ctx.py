import re

with open('src/oxt/pythonpath/extension/core/document_context.py', 'r') as f:
    content = f.read()

# Add import at the top
if 'from extension.utils.logger import log_error' not in content:
    content = content.replace('from typing import List, Dict, Optional, Any', 'from typing import List, Dict, Optional, Any\nfrom extension.utils.logger import log_error, log_warning')

# Replace except Exception: with except Exception as e: log_error("...", exc_info=True)
# But wait, there are too many and each should have a somewhat contextual message.
# For simplicity, we can do a regex replace if it's just `except Exception:` followed by `pass` or `return ""`
def replacer(match):
    indent = match.group(1)
    return f"{indent}except Exception as e:\n{indent}    log_warning(f\"DocumentContext non-fatal error: {{e}}\")"

# Wait, some are `except Exception: pass`, some are `except Exception: return ""`
# Let's just use python's AST or simply replace `except Exception:` with `except Exception as e:\n    log_warning(f"Error in DocumentContext: {e}")` if it's followed by `pass` or `return ""`
content = re.sub(r'([ \t]+)except Exception:\n\s+pass', r'\1except Exception as e:\n\1    log_warning(f"DocumentContext non-fatal error: {e}")', content)

content = re.sub(r'([ \t]+)except Exception:\n\s+return ""', r'\1except Exception as e:\n\1    log_warning(f"DocumentContext string extraction error: {e}")\n\1    return ""', content)

content = re.sub(r'([ \t]+)except Exception:\n\s+return (\[\]|\{\})', r'\1except Exception as e:\n\1    log_warning(f"DocumentContext extraction error: {e}")\n\1    return \2', content)


with open('src/oxt/pythonpath/extension/core/document_context.py', 'w') as f:
    f.write(content)

