
class Shorthand:
    """Class to elide name prefixes, giving us shorter versions of names."""

    def __init__(self, module, prefix):
        self.__mod = module
        self.__pfx = prefix

    def __getattr__(self, attr):
        val = getattr(self.__mod, self.__pfx + attr)
        setattr(self, attr, val)
        return val

