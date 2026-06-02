def show_msgbox(ctx, message, title="Error"):
    try:
        smgr = ctx.ServiceManager
        toolkit = smgr.createInstanceWithContext("com.sun.star.awt.Toolkit", ctx)
        # Note: In LibreOffice macros, we usually get the active window.
        # But we just want to know if Toolkit can create a messagebox.
        print("Toolkit created")
    except Exception as e:
        print(f"Failed: {e}")

