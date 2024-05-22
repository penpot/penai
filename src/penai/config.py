"""Contains configuration utils. In its current, default form, configuration will be read from config.json and
the git-ignored file config_local.json (you have to create it yourself if you need it) and merged. The config_local.json
is a good place to keep access keys and other secrets.
"""

import os

from accsr.config import ConfigProviderBase, DefaultDataConfiguration

file_dir = os.path.dirname(__file__) if "__file__" in locals() else os.getcwd()

top_level_directory: str = os.path.abspath(os.path.join(file_dir, os.pardir, os.pardir))


class __Configuration(DefaultDataConfiguration):
    pass


class ConfigProvider(ConfigProviderBase[__Configuration]):
    pass


_config_provider = ConfigProvider()


def get_config(reload: bool = False) -> __Configuration:
    """:param reload: if True, the configuration will be reloaded from the json files
    :return: the configuration instance
    """
    return _config_provider.get_config(reload=reload, config_directory=top_level_directory)
