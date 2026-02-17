import tkinter as tk
from app import LaserGuiApp


def main() -> None:
    root = tk.Tk()
    app = LaserGuiApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()