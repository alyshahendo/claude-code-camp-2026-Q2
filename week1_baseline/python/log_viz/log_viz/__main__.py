import os

from .app import create_app


def main():
    app = create_app()
    port = int(os.environ.get("PORT", "4567"))
    bind = os.environ.get("BIND", "localhost")
    app.run(host=bind, port=port)


if __name__ == "__main__":
    main()
