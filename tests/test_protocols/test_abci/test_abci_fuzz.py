# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
#
#   Copyright 2022 Valory AG
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

"""Test random initializations of ABCI Message content"""

from typing import Any, Dict

import hypothesis
import pytest
from hypothesis import given
from hypothesis import strategies as st
from hypothesis.strategies._internal.lazy import LazyStrategy, SearchStrategy

from tests.test_protocols.test_abci.helper import (
    AbciMessage,
    PYTHON_PRIMITIVES,
    Request,
    camel_to_snake,
    create_aea_abci_type_tree,
    decode,
    encode,
    get_protocol_readme_spec,
    get_tender_type_tree,
    get_tendermint_content,
    is_enum,
    replace_keys,
)


KEY_MAPPING = dict(  # AEA to Tendermint, one-to-one
    request_set_option={"key": "option_key", "value": "option_value"},
    request_query={"data": "query_data"},
    request_load_snapshot_chunk={"chunk": "chunk_index"},
    request_apply_snapshot_chunk={"sender": "chunk_sender"},
    response_info={"data": "info_data"},
)


key_translation = {
    "type_": "type",
    "format_": "format",
    "hash_": "hash",
    "round_": "round",
    "evidence_params": "evidence",
    "validator_params": "validator",
    "version_params": "version",
    "evidence_type": "type",
}


Node = Dict[str, Any]


BIT32 = 1 << 31
BIT64 = 1 << 63

STRATEGY_MAP = dict(  # TODO: strategy to assert failure
    int32=st.integers(min_value=-BIT32, max_value=BIT32 - 1),
    uint32=st.integers(min_value=0, max_value=(BIT32 << 1) - 1),
    int64=st.integers(min_value=-BIT64, max_value=BIT64 - 1),
    uint64=st.integers(min_value=0, max_value=(BIT64 << 1) - 1),
    bool=st.booleans(),
    string=st.text(),
    bytes=st.binary(),
    nanos=st.integers(min_value=0, max_value=10 ** 9 - 1),  # special case
)


# Step 1: retrieve tendermint protobuf type for primitives
def _translate(aea_type_node: Node, tender_type_node: Node) -> Node:
    """
    Translate type_node primitive to abci_node specification.

    Create a one-to-one mapping from Tendermint to AEA type tree.
    This is necessary because different types of integers are
    distinguished in protobuf: int32, uint32, int64, uint64.
    As long as the structure is maintained this can be used to
    initialize the AEA ABCIMessage instances.

    :param aea_type_node: mapping from message / field name to AEA type.
    :param tender_type_node: mapping from message / field name to Tendermint type.
    :return: mapping from message / field name to initialized primitive.
    """

    for key, type_child in aea_type_node.items():

        if is_enum(type_child):
            continue
        if key == "pub_key":
            type_child[-1]["data"] = "bytes"
            continue
        if key == "proof_ops" and "ops" in tender_type_node:
            _translate(type_child[-1][-1], tender_type_node["ops"][-1][-1])
            continue

        tender_key = key_translation.get(key, key)
        abci_child = tender_type_node[tender_key]

        if isinstance(type_child, str) or type_child in PYTHON_PRIMITIVES:
            aea_type_node[key] = abci_child
        elif is_enum(abci_child):
            continue
        elif isinstance(type_child, dict) and isinstance(abci_child, dict):
            _translate(type_child, abci_child)

        elif isinstance(type_child, tuple) and isinstance(abci_child, tuple):
            cls, d_type = type_child
            name, nested = abci_child
            if d_type in PYTHON_PRIMITIVES:
                aea_type_node[key] = cls, nested
            elif isinstance(d_type, dict) and isinstance(nested, dict):
                _translate(d_type, nested)
            elif isinstance(d_type, tuple):
                _translate(d_type[-1], nested[-1])
            else:  # extra nested mapping
                repeated = list(d_type.values())
                assert len(repeated) == 1
                _translate(repeated[0][-1][-1], nested[-1])
        else:
            raise NotImplementedError(f"{key}:\n{type_child}\n{abci_child}")

    return aea_type_node


def create_tender_type_tree(aea_type_tree: Node, tender_type_tree: Node) -> Node:
    """Create type tree with Tendermint primitives (as string)"""

    aea_with_tender_type_tree = {}
    for k, aea_type_node in aea_type_tree.items():
        tender_type_node = tender_type_tree[k][-1]
        replace_keys(tender_type_node, KEY_MAPPING.get(k, {}))  # type: ignore
        aea_with_tender_type_tree[k] = _translate(aea_type_node, tender_type_node)

    return aea_with_tender_type_tree


# 3. Create hypothesis strategies
def _init_subtree(node: Any) -> Any:
    """Initialize subtree with hypothesis strategies"""

    def init_repeated(repeated_type: Any) -> SearchStrategy:
        """Repeated fields must be tuples for Tendermint protobuf"""
        if isinstance(repeated_type, str) or repeated_type in PYTHON_PRIMITIVES:
            strategy = STRATEGY_MAP[repeated_type]
            return st.lists(strategy, min_size=0, max_size=100)
        elif isinstance(repeated_type, tuple):
            cls, kws = repeated_type
            strategy = st.builds(cls, **_init_subtree(kws))
            return st.lists(strategy, min_size=0, max_size=100)
        else:
            raise NotImplementedError(f"Repeated in {name}: {repeated_type}")

    if isinstance(node, str):
        return node

    kwargs: Node = {}
    for name, d_type in node.items():
        if isinstance(d_type, str) or d_type in PYTHON_PRIMITIVES:
            if name == "nanos":  # special case
                kwargs[name] = STRATEGY_MAP[name]
            else:
                kwargs[name] = STRATEGY_MAP[d_type]
        elif is_enum(d_type):
            kwargs[name] = st.sampled_from(list(d_type))
        elif isinstance(d_type, tuple):
            container, content = d_type
            if container is list:
                kwargs[name] = init_repeated(content)
            else:
                kwargs[name] = st.builds(container, **_init_subtree(content))
        else:
            raise NotImplementedError(f"{name}: {d_type}")

    return kwargs


def init_type_tree_hypotheses(type_tree: Node) -> Node:
    """
    Initialize the hypothesis strategies

    :param type_tree: mapping from message / field name to type.
    :return: mapping from message / field name to initialized primitive.
    """
    return {k: _init_subtree(node) for k, node in type_tree.items()}


def create_aea_hypotheses() -> Any:
    """Create hypotheses for ABCI Messages"""

    aea_protocol, *_ = get_protocol_readme_spec()
    speech_acts = aea_protocol["speech_acts"]

    # 1. create type tree from speech acts
    aea_type_tree = create_aea_abci_type_tree(speech_acts)
    aea_type_tree.pop("dummy")  # TODO: known oddity on our side

    # 2. create abci tree from Tendermint type definitions
    tender_type_tree = {camel_to_snake(k): v for k, v in get_tender_type_tree().items()}

    # 3. map the primitive types from ABCI spec onto the type tree
    aea_with_tender_type_tree = create_tender_type_tree(aea_type_tree, tender_type_tree)

    # 4. initialize with hypothesis
    hypo_tree = init_type_tree_hypotheses(aea_with_tender_type_tree)

    # 5. collapse hypo_tree
    def collapse(node: Node) -> Node:
        for k, v in node.items():
            if isinstance(v, dict):
                node[k] = st.fixed_dictionaries(collapse(v))
        return node

    return st.fixed_dictionaries(collapse(hypo_tree))


def init_abci_messages(type_tree: Node, init_tree: Node) -> Node:
    """Create ABCI messages for AEA-native ABCI spec"""

    messages = dict.fromkeys(type_tree)
    for key in type_tree:
        performative = getattr(AbciMessage.Performative, key.upper())
        messages[key] = AbciMessage(performative, **init_tree[key])

    return messages


# 4. Run hypotheses trees with valid strategies
@pytest.mark.skip  # Work in progress test
@given(create_aea_hypotheses())
@hypothesis.settings(deadline=500)
def test_aea_to_tendermint_hypotheses(strategy: Dict[str, LazyStrategy]) -> None:
    """Currently we check the encoding, data retrieval to be done."""

    def list_to_tuple(node: Node) -> Node:
        # expecting tuples instead of lists
        for k, v in node.items():
            if isinstance(v, dict):
                list_to_tuple(v)
            elif isinstance(v, list):
                node[k] = tuple(v)
        return node

    aea_protocol, *_ = get_protocol_readme_spec()
    speech_acts = aea_protocol["speech_acts"]
    type_tree = create_aea_abci_type_tree(speech_acts)
    type_tree.pop("dummy")

    abci_messages = init_abci_messages(type_tree, list_to_tuple(strategy))
    encoded = {k: encode(v) for k, v in abci_messages.items()}
    translated = {k: v for k, v in encoded.items() if v}
    untranslated = set(encoded).difference(translated)
    assert all(k.startswith("request") for k in untranslated)

    tender_tree = {k: get_tendermint_content(v) for k, v in translated.items()}
    shared = set(type_tree).intersection(tender_tree)
    assert len(shared) == 16, shared  # expected number of matches


# tendermint fuzzing
def _init_tender_hypo_tree(tender_node: Node) -> Node:
    """Initialize Tendermint classes"""

    def init_repeated(repeated_type: Any) -> SearchStrategy:
        if isinstance(repeated_type, str):
            strategy = STRATEGY_MAP[repeated_type]
            return st.lists(strategy, min_size=0, max_size=100)
        cls, kwargs = repeated_type
        strategy = st.builds(cls, **_init_tender_hypo_tree(kwargs))
        return st.lists(strategy, min_size=0, max_size=100)

    node = {}
    for field, d_type in tender_node.items():
        if isinstance(d_type, str):
            if field == "nanos":  # special
                node[field] = STRATEGY_MAP[field]
            else:
                node[field] = STRATEGY_MAP[d_type]
        elif is_enum(d_type):
            node[field] = st.sampled_from([f.value for f in d_type])
        elif isinstance(d_type, tuple):
            container, content = d_type
            if container is list:
                node[field] = init_repeated(content)
            else:
                node[field] = st.builds(container, **_init_tender_hypo_tree(content))
        else:
            raise NotImplementedError(f"field {field}: {d_type}")

    return node


def create_tendermint_hypotheses() -> SearchStrategy:
    """Create Tendermint hypotheses"""
    tender_type_tree = get_tender_type_tree()
    _, request_tree = tender_type_tree["Request"]
    tender_hypo_tree = _init_tender_hypo_tree(request_tree)
    return st.fixed_dictionaries(tender_hypo_tree)


@pytest.mark.skip  # Work in progress test
@given(create_tendermint_hypotheses())
@hypothesis.settings(deadline=500)
def test_tendermint_to_aea_hypotheses(strategy: Dict[str, LazyStrategy]) -> None:
    """Test translation Tendermint- to AEA-native ABCI Messages"""

    messages = [Request(**{k: v}) for k, v in strategy.items()]
    decoded = list(map(decode, messages))
    assert len(decoded) == 15  # expected number of matches
