"""Contains configuration utils. In its current, default form, configuration will be read from config.json and
the git-ignored file config_local.json (you have to create it yourself if you need it) and merged. The config_local.json
is a good place to keep access keys and other secrets.

The configuration relies on runtime usage of generics, which might be unfamiliar to some python users. If you don't
fully understand what is going on here, you don't need to worry too much about it (although in that case it would be
useful to read the source code docu in accsr). In essence:

    1.  The `__Configuration` class is where you put your custom configuration getters. Since here it inherits from
        `DefaultDataConfiguration`, you already have some default getter methods like `data_raw`, `data_processed`
        and so on. You will probably want to extend this
        class with more getters for your config needs.
        A typical example that is often used at appliedAI is to include a remote storage config
        (for which there is also support in accsr), with
        .. code-block:: python
            @property
            def remote_storage(self):
                return RemoteStorageConfig(**self._get_non_empty_entry("remote_storage_config"))

        but you can include anything you want.
    2.  The `ConfigProvider` related things are there to provides instances of `__Configuration` without having to
        reload it from disc, unless specifically desired. Essentially, it is a singleton provider. Most likely you
        will not need to adjust it and just use the `get_config` function to retrieve your config.
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
