try:
    from ipydex import Container

    class ResultContainer(Container):
        pass
except ImportError:
    # this might be relevant during the installation process
    # otherwise setup.py cannot be executed
    pass

from .release import __version__
