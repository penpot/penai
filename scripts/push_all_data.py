from jsonargparse import CLI

from penai.config import DataStage, get_config, push_to_remote


def push_all_data(stage: DataStage = "raw", force: bool = False) -> None:
    """Pushes all data in the desired stage to the remote storage.

    :param stage: the stage for which the data should be pushed
    :param force: if True, the remote files might be overwritten
    """
    c = get_config()
    target_dir = c.data_basedir(stage=stage, check_existence=True)
    print(f"Pushing data for stage {stage} from {target_dir}")
    push_to_remote(c.data_basedir(stage=stage), force=force)


if __name__ == "__main__":
    CLI(push_all_data)
