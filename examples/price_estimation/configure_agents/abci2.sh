#!/usr/bin/env sh

cp ../configure_agents/keys/ethereum_private_key_2.txt ethereum_private_key.txt
aea config set vendor.valory.skills.price_estimation_abci.models.price_api.args.source_id coinbase
aea config set vendor.valory.skills.price_estimation_abci.models.params.args.consensus.max_participants 4
aea config set vendor.valory.skills.price_estimation_abci.models.params.args.tendermint_url http://node2:26657
aea config set vendor.valory.skills.price_estimation_abci.models.params.args.ethereum_node_url http://hardhat:8545
aea config set vendor.valory.skills.price_estimation_abci.models.params.args.proxy_contract_address "0x8C63F2A488B3Cf2Eb8439bB92757a0A760E70942"
aea build
