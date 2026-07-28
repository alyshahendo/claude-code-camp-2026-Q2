from .base import Base


class Player(Base):
    """The main loop task."""

    @classmethod
    def task_name(cls):
        return "player"
