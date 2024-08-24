""" Runs docker containers locally.

This is handy for testing if dockerfiles work with powerlift before
sending it a remote container service.
"""

from powerlift.bench.store import Store
from powerlift.executors.localmachine import LocalMachine
from powerlift.executors.base import handle_err
from typing import Iterable, List
import multiprocessing


def _run_docker(experiment_id, runner_id, db_url, timeout, raise_exception, image):
    import docker

    client = docker.from_env()

    container = client.containers.run(
        image,
        "python -m powerlift.run",
        environment={
            "EXPERIMENT_ID": experiment_id,
            "RUNNER_ID": runner_id,
            "DB_URL": db_url,
            "TIMEOUT": timeout,
            "RAISE_EXCEPTION": raise_exception,
        },
        network_mode="host",
        detach=True,
    )
    exit_code = container.wait()
    container.remove()
    return exit_code


class InsecureDocker(LocalMachine):
    """Runs trials in local docker containers.

    Make sure the machine you run on is fully trusted.
    Environment variables are used to pass the database connection string,
    which means other users on the machine may be able to see it via enumerating
    the processes on the machine and their args.
    """

    def __init__(
        self,
        store: Store,
        image: str = "interpretml/powerlift:0.1.11",
        n_running_containers: int = None,
        wheel_filepaths: List[str] = None,
        docker_db_uri: str = None,
        raise_exception: bool = False,
    ):
        """Runs trials in local docker containers.

        Args:
            store (Store): Store that houses trials.
            image (str, optional): Image to execute in container. Defaults to "interpretml/powerlift:0.0.1".
            n_running_containers (int, optional): Max number of containers running simultaneously. Defaults to None.
            wheel_filepaths (List[str], optional): List of wheel filepaths to install on docker trial run. Defaults to None.
            docker_db_uri (str, optional): Database URI for container. Defaults to None.
            raise_exception (bool, optional): Raise exception on failure.
        """
        self._docker_db_uri = docker_db_uri
        self._image = image
        super().__init__(
            store=store,
            n_cpus=n_running_containers,
            raise_exception=raise_exception,
            wheel_filepaths=wheel_filepaths,
        )

    def submit(self, experiment_id, trial_run_fn, trials: List, timeout=None):
        uri = (
            self._docker_db_uri if self._docker_db_uri is not None else self._store.uri
        )
        self._store.add_trial_run_fn([x.id for x in trials], trial_run_fn)

        n_runners = min(
            len(trials),
            multiprocessing.cpu_count() if self._n_cpus is None else self._n_cpus,
        )
        for runner_id in range(n_runners):
            self._runner_id_to_result[runner_id] = self._pool.apply_async(
                _run_docker,
                (
                    experiment_id,
                    runner_id,
                    uri,
                    timeout,
                    self._raise_exception,
                    self._image,
                ),
                error_callback=handle_err,
            )

    @property
    def docker_db_uri(self):
        return self._docker_db_uri

    @property
    def image(self):
        return self._image
