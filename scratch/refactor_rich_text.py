import re

with open('src/oxt/pythonpath/extension/core/rich_text.py', 'r') as f:
    content = f.read()

if 'from extension.utils.logger import log_error' not in content:
    content = content.replace('from typing import List, Dict, Optional, Tuple', 'from typing import List, Dict, Optional, Tuple\nfrom extension.utils.logger import log_error, log_warning')

content = re.sub(r'([ \t]+)except Exception:\s*\n\s+pass', r'\1except Exception as e:\n\1    log_warning(f"RichText formatting error: {e}")', content)

content = re.sub(r'([ \t]+)except Exception: pass', r'\1except Exception as e:\n\1    log_warning(f"RichText formatting error: {e}")', content)

content = re.sub(r'([ \t]+)except Exception:\n\s+return', r'\1except Exception as e:\n\1    log_error(f"RichText execution error: {e}", exc_info=True)\n\1    return', content)

content = re.sub(r'([ \t]+)except Exception:\n\s+self\._text\.insertControlCharacter', r'\1except Exception as e:\n\1    log_warning(f"RichText fallback to control char: {e}")\n\1    self._text.insertControlCharacter', content)


with open('src/oxt/pythonpath/extension/core/rich_text.py', 'w') as f:
    f.write(content)

