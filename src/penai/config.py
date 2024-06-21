"""Contains configuration and remote storage utils.
In its current, default form, configuration will be read from `config.json` and
the git-ignored file `config_local.json` (you have to create it yourself if you need it) and merged.
The `config_local.json` is a good place to keep access keys and other secrets.
"""

import os
from pathlib import Path
from re import Pattern
from typing import Literal, cast

from accsr.config import ConfigProviderBase, DefaultDataConfiguration
from accsr.remote_storage import RemoteStorage, RemoteStorageConfig, TransactionSummary
from openai import OpenAI

file_dir = os.path.dirname(__file__) if "__file__" in locals() else os.getcwd()

top_level_directory: str = os.path.abspath(os.path.join(file_dir, os.pardir, os.pardir))

DataStage = Literal["raw", "processed", "cleaned", "ground_truth"]


class __Configuration(DefaultDataConfiguration):
    @property
    def remote_storage(self) -> RemoteStorageConfig:
        storage_config = cast(dict, self._get_non_empty_entry("remote_storage_config"))
        return RemoteStorageConfig(**storage_config)

    def data_basedir(
        self,
        stage: DataStage = "raw",
        relative: bool = False,
        check_existence: bool = False,
    ) -> str:
        result = self._data_basedir(stage)
        return self._adjusted_path(result, relative=relative, check_existence=check_existence)

    def penpot_designs_basedir(self, relative: bool = False, check_existence: bool = False) -> str:
        result = self.datafile_path("designs", stage="raw")
        return self._adjusted_path(result, relative=relative, check_existence=check_existence)

    @property
    def openai_api_key(self) -> str:
        return cast(str, self._get_non_empty_entry(["api_keys", "openai"]))

    @property
    def anthropic_api_key(self) -> str:
        return cast(str, self._get_non_empty_entry(["api_keys", "anthropic"]))

    @property
    def gemini_api_key(self) -> str:
        return cast(str, self._get_non_empty_entry(["api_keys", "gemini"]))

    def get_openai_client(self, timeout: int = 100) -> OpenAI:
        return OpenAI(api_key=self.openai_api_key, timeout=timeout)

    @property
    def penpot_user(self) -> str:
        return cast(str, self._get_non_empty_entry(["penpot_backend", "user"]))

    @property
    def penpot_password(self) -> str:
        return cast(str, self._get_non_empty_entry(["penpot_backend", "password"]))

    @property
    def cache_dir(self) -> str:
        """:return: absolute path to directory where cache files are stored"""
        return self._get_existing_path("cache", create=True)

    @property
    def temp_cache_dir(self) -> str:
        """:return: absolute path to directory where temporary cache files are stored"""
        return self._get_existing_path("temp_cache", create=True)

    @property
    def llm_responses_cache_path(self) -> str:
        return str(Path(self.cache_dir) / self._get_non_empty_entry("llm_responses_cache_filename"))

    def results_dir(self) -> str:
        return self._get_existing_path("results", create=True)


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
