from . import __version__
from .gui import MainWindow


def main() -> None:
    print(f"syno-photo-tidy v{__version__}")
    app = MainWindow()
    app.run()
