#!/usr/bin/env sh

cp ../configure_agents/keys/ethereum_private_key_2.txt ethereum_private_key.txt
aea config set vendor.valory.skills.price_estimation_abci.models.price_api.args.source_id coinbase
aea config set vendor.valory.skills.price_estimation_abci.models.randomness_api.args.source_id protocollabs2
aea config set vendor.valory.skills.price_estimation_abci.models.params.args.consensus.max_participants 4
aea config set vendor.valory.skills.price_estimation_abci.models.params.args.keeper_timeout_seconds 5
aea config set vendor.valory.skills.price_estimation_abci.models.params.args.tendermint_url http://node2:26657
aea config set vendor.valory.connections.ledger.config.ledger_apis.ethereum.address  "https://ropsten.infura.io/v3/2980beeca3544c9fbace4f24218afcd4"
aea config set vendor.valory.connections.ledger.config.ledger_apis.ethereum.chain_id  3
aea build
