import sys
import os

# ---- AGGRESSIVE DEPENDENCY RESOLUTION ----
# LibreOffice often loads system Python packages (like typing_extensions) before our extension.
# We must force our vendored 'pythonpath' to the absolute front of sys.path.
extension_path = None
for p in sys.path:
    if "Neuro_AI.oxt" in p or "pythonpath" in p:
        if os.path.exists(os.path.join(p, "extension")):
            extension_path = p
            break

if extension_path:
    sys.path.remove(extension_path)
    sys.path.insert(0, extension_path)
    # Force unload system typing_extensions if LibreOffice already loaded it
    if "typing_extensions" in sys.modules:
        mod = sys.modules["typing_extensions"]
        if hasattr(mod, "__file__") and mod.__file__ and "/usr/lib" in mod.__file__:
            del sys.modules["typing_extensions"]
# ------------------------------------------

import uno
import unohelper

from com.sun.star.frame import XDispatchProvider, XDispatch
from com.sun.star.lang import XServiceInfo
from com.sun.star.task import XJobExecutor

IMPLEMENTATION_NAME = "org.neuro.ai.libreoffice.extension.MainComponent"
PROTOCOL_PREFIX = "org.neuro.ai.libreoffice.extension:"


class Dispatcher(unohelper.Base, XDispatch):
    def __init__(self, ctx, command):
        self.ctx = ctx
        self.command = command

    def dispatch(self, url, arguments):
        action = url.Path

        desktop = self.ctx.ServiceManager.createInstanceWithContext(
            "com.sun.star.frame.Desktop", self.ctx
        )
        doc = desktop.getCurrentComponent()

        if action in ("GenerateText", "ProcessData", "RewriteSelection", "SummarizeSelection", "AskDocument"):
            self._open_chat(doc, action)

    def _open_chat(self, doc, action):
        """Open the Neuro AI Chat dialog and optionally trigger an action."""
        try:
            from extension.ui.chat_dialog import ChatDialog
            global _active_chat
            _active_chat = ChatDialog(self.ctx, doc)
            _active_chat.show()
            
            # Map action to UI quick action if requested
            action_map = {
                "RewriteSelection": "rewrite",
                "SummarizeSelection": "summarize",
                "AskDocument": "doc_qa"
            }
            if action in action_map:
                _active_chat.send_message(action=action_map[action])
                
        except Exception as e:
            # Fallback: show error in a message box
            self._show_error(str(e))

    def _show_error(self, message):
        """Show an error message box."""
        try:
            smgr = self.ctx.ServiceManager
            desktop = smgr.createInstanceWithContext(
                "com.sun.star.frame.Desktop", self.ctx
            )
            frame = desktop.getCurrentFrame()
            window = frame.getContainerWindow()
            toolkit = smgr.createInstanceWithContext(
                "com.sun.star.awt.Toolkit", self.ctx
            )
            msgbox = toolkit.createMessageBox(
                window, 0, 1, "Neuro AI Error", f"Failed to open chat:\n{message}"
            )
            msgbox.execute()
        except Exception:
            print(f"[Neuro AI Error]: {message}")

    def addStatusListener(self, control, url):
        pass

    def removeStatusListener(self, control, url):
        pass


class MainComponent(unohelper.Base, XDispatchProvider, XServiceInfo, XJobExecutor):
    def __init__(self, ctx):
        self.ctx = ctx

    # XDispatchProvider
    def queryDispatch(self, url, name, searchFlags):
        if url.Protocol == PROTOCOL_PREFIX:
            return Dispatcher(self.ctx, url.Path)
        return None

    def queryDispatches(self, requests):
        return tuple(
            self.queryDispatch(req.FeatureURL, req.FrameName, req.SearchFlags)
            for req in requests
        )

    # XServiceInfo
    def supportsService(self, name):
        return name in self.getSupportedServiceNames()

    def getImplementationName(self):
        return IMPLEMENTATION_NAME

    def getSupportedServiceNames(self):
        return (IMPLEMENTATION_NAME, "com.sun.star.frame.ProtocolHandler")

    # XJobExecutor
    def trigger(self, arg):
        pass


# Component factory function
def create(ctx, *args):
    return MainComponent(ctx)


g_ImplementationHelper = unohelper.ImplementationHelper()
g_ImplementationHelper.addImplementation(
    create,
    IMPLEMENTATION_NAME,
    (IMPLEMENTATION_NAME, "com.sun.star.frame.ProtocolHandler"),
)
