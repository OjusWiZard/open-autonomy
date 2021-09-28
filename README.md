# Consensus algorithms

Distributed consensus meets the AEA framework.

## Preliminaries

- Clone the repository, and recursively clone the submodules:

      git clone --recursive git@github.com:valory-xyz/consensus-algorithms.git

  Later to update the Git submodules:

      git submodule update --init --recursive

- Create and launch a virtual environment with Python 3.8 (any Python `>=` 3.6 works):

      pipenv --python 3.8 && pipenv shell
      pip install "aea-ledger-ethereum>=1.0.0,<2.0.0" --no-deps

  We need to add `--no-deps` flag because of conflicting subdependencies.
  You can ignore the error message from the command `pip install`.

- Install the package from source:

      pip install -e .

- [Install Tendermint](https://docs.tendermint.com/master/introduction/install.html)
- Build the Hardhat project:

      cd third_party/safe-contracts && yarn

## During development:

- Install development dependencies:

      pipenv install --dev --skip-lock
      pip install "aea-ledger-ethereum>=1.0.0,<2.0.0" --no-deps

- Install [IPFS node](https://docs.ipfs.io/install/command-line/#official-distributions) `v0.6.0`
 
- Clone the `packages/fetchai` from the AEA framework repository in `packages/`:

      svn export https://github.com/fetchai/agents-aea/tags/v1.0.2/packages/fetchai packages/fetchai