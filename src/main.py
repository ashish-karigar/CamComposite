# main.py
import sys
from pathlib import Path
print("RUNNING FROM:", Path(__file__).resolve(), "\nEXE:", sys.executable, "\nCWD:", Path.cwd(), "\nSYS.PATH[0:5]:", sys.path[:5])
from app import CamCompositeApp


if __name__ == "__main__":
    app = CamCompositeApp()
    app.mainloop()