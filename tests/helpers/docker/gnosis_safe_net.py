# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2021 Valory AG
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#
# ------------------------------------------------------------------------------

"""Tendermint Docker image."""
import logging
import time
from typing import List

import docker
import requests
from aea.exceptions import AEAEnforceError, enforce
from docker.models.containers import Container

from tests.helpers.constants import THIRD_PARTY
from tests.helpers.docker.base import DockerImage


DEFAULT_HARDHAT_PORT = 8545
GNOSIS_SAFE_CONTRACTS_ROOT_DIR = THIRD_PARTY / "safe-contracts"

_SLEEP_TIME = 1

# Note: addresses of deployment of master contracts are deterministic
SAFE_CONTRACT = "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"
DEFAULT_CALLBACK_HANDLER = "0xf48f2B2d2a534e402487b3ee7C18c33Aec0Fe5e4"
PROXY_FACTORY_CONTRACT = "0xa6B71E26C5e0845f74c812102Ca7114b6a896AB2"
MULTISEND_CONTRACT = "0xA238CBeb142c10Ef7Ad8442C6D1f9E89e07e7761"
MULTISEND_CALL_ONLY_CONTRACT = "0x40A2aCCbd92BCA938b02010E17A5b8929b49130D"


class GnosisSafeNetDockerImage(DockerImage):
    """Spawn a local Ethereum network with deployed Gnosis Safe contracts, using HardHat."""

    def __init__(
        self,
        client: docker.DockerClient,
        port: int = DEFAULT_HARDHAT_PORT,
    ):
        """Initialize."""
        super().__init__(client)
        self.port = port

    @property
    def tag(self) -> str:
        """Get the tag."""
        return "node:16.7.0"

    def _build_command(self) -> List[str]:
        """Build command."""
        cmd = ["run", "hardhat", "node", "--port", str(self.port)]
        return cmd

    def create(self) -> Container:
        """Create the container."""
        cmd = self._build_command()
        working_dir = "/build"
        volumes = {
            str(GNOSIS_SAFE_CONTRACTS_ROOT_DIR): {
                "bind": working_dir,
                "mode": "rw",
            },
        }
        container = self._client.containers.run(
            self.tag,
            command=cmd,
            detach=True,
            network="host",
            volumes=volumes,
            working_dir=working_dir,
            entrypoint="yarn",
        )
        return container

    def wait(self, max_attempts: int = 15, sleep_rate: float = 1.0) -> bool:
        """
        Wait until the image is running.

        :param max_attempts: max number of attempts.
        :param sleep_rate: the amount of time to sleep between different requests.
        :return: True if the wait was successful, False otherwise.
        """
        request = dict(jsonrpc=2.0, method="web3_clientVersion", params=[], id=1)
        for i in range(max_attempts):
            try:
                response = requests.post(f"http://localhost:{self.port}", json=request)
                enforce(response.status_code == 200, "")
                return True
            except (AEAEnforceError, requests.ConnectionError, requests.ConnectTimeout):
                logging.info(
                    "Attempt %s failed. Retrying in %s seconds...", i, sleep_rate
                )
                time.sleep(sleep_rate)
        return False
