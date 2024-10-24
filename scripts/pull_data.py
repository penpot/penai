from jsonargparse import CLI

from penai.config import DataStage, get_config, pull_from_remote
from penai.utils.argparse import HandleFlagsArgumentParser


def pull_data(
    stage: DataStage = "raw", force: bool = False, include_llm_cache: bool = True
) -> None:
    """Pulls all data in the desired stage from the remote storage.

    :param stage: the stage for which the data should be pulled
    :param force: if True, the local files might be overwritten
    :param include_llm_cache: if True, the LLM cache will be pulled as well
    """
    c = get_config()
    target_dir = c.data_basedir(stage=stage)
    print(f"Pulling data for stage {stage} to {target_dir}")
    pull_from_remote(c.data_basedir(stage=stage), force=force)
    if include_llm_cache:
        pull_from_remote(c.llm_responses_cache_path, force=force)


if __name__ == "__main__":
    CLI(pull_data, parser_class=HandleFlagsArgumentParser)
