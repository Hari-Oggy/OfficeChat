# -*- coding: utf-8 -*-
# =============================================================================
# ui_utils.py — UI Utilities for Neuro AI (e.g. Message Boxes)
# =============================================================================

from extension.utils.logger import log_error

try:
    import uno
    from com.sun.star.awt import MessageBoxButtons
    from com.sun.star.awt.MessageBoxType import (
        MESSAGEBOX, INFOBOX, WARNINGBOX, ERRORBOX, QUERYBOX
    )
except ImportError:
    uno = None

def show_message_box(ctx, peer, message: str, title: str = "Neuro AI", type_str: str = "error"):
    """
    Displays a native LibreOffice message box.
    
    Parameters
    ----------
    ctx : XComponentContext
        The UNO component context.
    peer : XWindowPeer
        The parent window peer (e.g. dialog.getPeer()).
    message : str
        The message to display.
    title : str
        The title of the message box.
    type_str : str
        One of 'info', 'warning', 'error', 'query'.
    """
    if not uno or not ctx or not peer:
        return

    try:
        smgr = ctx.ServiceManager
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        
        box_type = ERRORBOX
        if type_str == "info":
            box_type = INFOBOX
        elif type_str == "warning":
            box_type = WARNINGBOX
        elif type_str == "query":
            box_type = QUERYBOX
            
        msgbox = toolkit.createMessageBox(
            peer,
            box_type,
            MessageBoxButtons.BUTTONS_OK,
            title,
            message
        )
        msgbox.execute()
    except Exception as e:
        log_error(f"Failed to display message box: {e}", exc_info=True)
