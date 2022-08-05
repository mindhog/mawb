"""OOP wrapper around LILV."""

import lilv
from typing import Any, Dict, Generator

def _as_str(node: 'LilvNode') -> str:
    return lilv.lilv_node_as_string(node)

class Port:
    def __init__(self, plugin: 'LilvPlugin', port: 'LilvPort'):
        self.__plugin = plugin
        self.__port = port
        self.__range = None

    @property
    def name(self):
        return _as_str(lilv.lilv_port_get_name(self.__plugin, self.__port))

    @property
    def symbol(self):
        return _as_str(lilv.lilv_port_get_symbol(self.__plugin, self.__port))

    @property
    def min(self):
        if not self.__range:
            self.__range = lilv.lilv_port_get_range(self.__plugin, self.__port)
        return self.__range[1]

    @property
    def max(self):
        if not self.__range:
            self.__range = lilv.lilv_port_get_range(self.__plugin, self.__port)
        return self.__range[2]

    @property
    def default(self):
        if not self.__range:
            self.__range = lilv.lilv_port_get_range(self.__plugin, self.__port)
        return self.__range[0]

    def to_dict(self):
        return {'name': self.name,
                'symbol': self.symbol,
                'default': self.default,
                'min': self.min,
                'max': self.max}

class Plugin:
    def __init__(self, plugin: 'LilvPlugin') -> None:
        self.__plugin = plugin
        self.__ports = None

    @property
    def name(self):
        return lilv.lilv_node_as_string(
            lilv.lilv_plugin_get_name(self.__plugin)
        )

    @property
    def uri(self):
        return lilv.lilv_node_as_string(
            lilv.lilv_plugin_get_uri(self.__plugin)
        )

    @property
    def ports(self):
        if self.__ports is None:
            self.__ports = []
            num_ports = lilv.lilv_plugin_get_num_ports(self.__plugin)
            self.__ports = [
                Port(self.__plugin,
                     lilv.lilv_plugin_get_port_by_index(self.__plugin, i))
                for i in range(num_ports)
            ]
        return self.__ports

    def to_dict(self) -> Dict[str, Any]:
        return {'ports': [port.to_dict() for port in self.ports],
                'name': self.name,
                'uri': self.uri}

class PluginWorld:
    """The complete "lilv" environment.

    This is mainly just used to load the list of plugins in the system.
    """
    def __init__(self):
        self.__lilv = lilv.lilv_world_new()
        lilv.lilv_world_load_all(self.__lilv)

    def __del__(self):
        lilv.lilv_world_free(self.__lilv)

    def plugins(self) -> Generator[Plugin, None, None]:
        """Returns a generator over the set of plugins."""
        plugins = lilv.lilv_world_get_all_plugins(self.__lilv)
        iter = lilv.lilv_plugins_begin(plugins)
        while not lilv.lilv_plugins_is_end(plugins, iter):
            yield Plugin(lilv.lilv_plugins_get(plugins, iter))
            iter = lilv.lilv_plugins_next(plugins, iter)

if __name__ == '__main__':
    import pprint
    pprint.pprint([p.to_dict() for p in PluginWorld().plugins()])
