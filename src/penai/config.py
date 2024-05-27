"""Contains configuration and remote storage utils.
In its current, default form, configuration will be read from `config.json` and
the git-ignored file `config_local.json` (you have to create it yourself if you need it) and merged.
The `config_local.json` is a good place to keep access keys and other secrets.
"""

import os
from re import Pattern
from typing import cast

from accsr.config import ConfigProviderBase, DefaultDataConfiguration
from accsr.remote_storage import RemoteStorage, RemoteStorageConfig, TransactionSummary
from openai import OpenAI

file_dir = os.path.dirname(__file__) if "__file__" in locals() else os.getcwd()

top_level_directory: str = os.path.abspath(os.path.join(file_dir, os.pardir, os.pardir))


class __Configuration(DefaultDataConfiguration):
    @property
    def remote_storage(self) -> RemoteStorageConfig:
        storage_config = cast(dict, self._get_non_empty_entry("remote_storage_config"))
        return RemoteStorageConfig(**storage_config)

    @property
    def openai_api_key(self) -> str:
        return cast(str, self._get_non_empty_entry("openai_api_key"))

    def get_openai_client(self, timeout: int = 100) -> OpenAI:
        return OpenAI(api_key=self.openai_api_key, timeout=timeout)


class ConfigProvider(ConfigProviderBase[__Configuration]):
    pass


_config_provider = ConfigProvider()


def get_config(reload: bool = False) -> __Configuration:
    """:param reload: if True, the configuration will be reloaded from the json files
    :return: the configuration instance
    """
    return _config_provider.get_config(reload=reload, config_directory=top_level_directory)


__remote_storage_instance = None


def default_remote_storage() -> RemoteStorage:
    """Returns the default remote storage instance. It is created lazily."""
    global __remote_storage_instance
    if __remote_storage_instance is None:
        __remote_storage_instance = RemoteStorage(get_config().remote_storage)
    return __remote_storage_instance


def pull_from_remote(
    remote_path: str,
    force: bool = False,
    include_regex: Pattern | str | None = None,
    exclude_regex: Pattern | str | None = None,
    dryrun: bool = False,
) -> TransactionSummary:
    """Pulls from the remote storage using the default storage config."""
    return default_remote_storage().pull(
        remote_path=remote_path,
        local_base_dir=top_level_directory,
        force=force,
        include_regex=include_regex,
        exclude_regex=exclude_regex,
        dryrun=dryrun,
    )


def push_to_remote(
    local_path: str,
    force: bool = False,
    include_regex: Pattern | str | None = None,
    exclude_regex: Pattern | str | None = None,
    dryrun: bool = False,
) -> TransactionSummary:
    """Pushes to the remote storage using the default storage config."""
    return default_remote_storage().push(
        path=local_path,
        local_path_prefix=top_level_directory,
        include_regex=include_regex,
        exclude_regex=exclude_regex,
        force=force,
        dryrun=dryrun,
    )
