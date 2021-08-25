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

"""This module contains the data classes for the price estimation ABCI application."""
from abc import ABC
from collections import Counter
from operator import itemgetter
from types import MappingProxyType
from typing import Any
from typing import Counter as CounterType
from typing import Dict, FrozenSet, Mapping, Optional, Set, Tuple, cast

from aea.exceptions import enforce

from packages.valory.skills.abstract_round_abci.base_models import AbstractRound
from packages.valory.skills.price_estimation_abci.models.payloads import (
    DeploySafePayload,
    EstimatePayload,
    ObservationPayload,
    RegistrationPayload,
    SignaturePayload,
)
from packages.valory.skills.price_estimation_abci.params import ConsensusParams


class PeriodState:
    """Class to represent a period state."""

    def __init__(
        self,
        participants: Optional[FrozenSet[str]] = None,
        safe_contract_address: Optional[str] = None,
        participant_to_observations: Optional[Mapping[str, ObservationPayload]] = None,
        participant_to_estimate: Optional[Mapping[str, EstimatePayload]] = None,
        most_voted_estimate: Optional[float] = None,
        participant_to_signature: Optional[Mapping[str, str]] = None,
    ) -> None:
        """Initialize a period state."""
        self._participants = participants
        self._safe_contract_address = safe_contract_address
        self._participant_to_observations = participant_to_observations
        self._participant_to_estimate = participant_to_estimate
        self._most_voted_estimate = most_voted_estimate
        self._participant_to_signature = participant_to_signature

    @property
    def participants(self) -> FrozenSet[str]:
        """Get the participants."""
        enforce(self._participants is not None, "'participants' field is None")
        return cast(FrozenSet[str], self._participants)

    @property
    def safe_contract_address(self) -> str:
        """Get the safe contract address."""
        enforce(
            self._safe_contract_address is not None,
            "'safe_contract_address' field is None",
        )
        return cast(str, self._safe_contract_address)

    @property
    def participant_to_observations(self) -> Mapping[str, ObservationPayload]:
        """Get the participant_to_observations."""
        enforce(
            self._participant_to_observations is not None,
            "'participant_to_observations' field is None",
        )
        return cast(Mapping[str, ObservationPayload], self._participant_to_observations)

    @property
    def participant_to_estimate(self) -> Mapping[str, EstimatePayload]:
        """Get the participant_to_estimate."""
        enforce(
            self._participant_to_estimate is not None,
            "'participant_to_estimate' field is None",
        )
        return cast(Mapping[str, EstimatePayload], self._participant_to_estimate)

    @property
    def participant_to_signature(self) -> Mapping[str, str]:
        """Get the participant_to_signature."""
        enforce(
            self._participant_to_estimate is not None,
            "'participant_to_signature' field is None",
        )
        return cast(Mapping[str, str], self._participant_to_signature)

    @property
    def most_voted_estimate(self) -> float:
        """Get the most_voted_estimate."""
        enforce(
            self._most_voted_estimate is not None, "'most_voted_estimate' field is None"
        )
        return cast(float, self._most_voted_estimate)

    @property
    def observations(self) -> Tuple[ObservationPayload, ...]:
        """Get the tuple of observations."""
        return tuple(self.participant_to_observations.values())

    @property
    def safe_sender_address(self) -> str:
        """
        Get the Safe sender address.

        It is the address with the minimum integer value,
        and since the length of the hex strings is the same,
        this coincides with alphanumeric order.

        However, we need to lower the strings, since
        the addresses are checksum addres.

        TOFIX: the 'leader' should be decided in a more sensible way,
          introducing some decentralized randomization. this is a
          temporary solution.

        :return: the sender address
        """
        return min(self.participants, key=str.lower)

    def update(self, **kwargs) -> "PeriodState":
        """Copy and update the state."""
        # remove leading underscore from keys
        data = {key[1:]: value for key, value in self.__dict__.items()}
        data.update(kwargs)
        return PeriodState(**data)


class BaseRound(AbstractRound, ABC):
    """Base round class for the price_estimation_abci skill."""

    def __init__(
        self,
        state: PeriodState,
        consensus_params: ConsensusParams,
        *args: Any,
        **kwargs: Any
    ) -> None:
        """Initialize the base round."""
        super().__init__(*args, **kwargs)
        self._consensus_params = consensus_params
        self._state = state

    @property
    def state(self) -> PeriodState:
        """Get the period state."""
        return self._state


class RegistrationRound(BaseRound):
    """
    This class represents the registration round.

    Input: None
    Output: a period state with the set of participants.

    It schedules the DeploySafeRound.
    """

    round_id = "registration"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the registration round."""
        super().__init__(*args, **kwargs)

        # a collection of addresses
        self.participants: Set[str] = set()

    def registration(self, payload: RegistrationPayload) -> None:
        """Handle a registration payload."""
        sender = payload.sender

        # we don't care if it was already there
        self.participants.add(sender)

    def check_registration(  # pylint: disable=no-self-use
        self, _payload: RegistrationPayload
    ) -> bool:
        """
        Check a registration payload can be applied to the current state.

        A registration can happen only when we are in the registration state.

        :param: _payload: the payload.
        :return: True.
        """
        return True

    @property
    def registration_threshold_reached(self) -> bool:
        """Check that the registration threshold has been reached."""
        return len(self.participants) == self._consensus_params.max_participants

    def end_block(self) -> Optional[Tuple[PeriodState, Optional["AbstractRound"]]]:
        """Process the end of the block."""
        # if reached participant threshold, set the result
        if self.registration_threshold_reached:
            state = PeriodState(participants=frozenset(self.participants))
            next_round = DeploySafeRound(state, self._consensus_params)
            return state, next_round
        return None


class DeploySafeRound(BaseRound):
    """
    This class represents the deploy Safe round.

    Input: a set of participants (addresses)
    Output: a period state with the set of participants and the Safe contract address.

    It schedules the CollectObservationRound.
    """

    round_id = "deploy_safe"

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the 'collect-observation' round."""
        super().__init__(*args, **kwargs)
        self._contract_address: Optional[str] = None

    def deploy_safe(self, payload: DeploySafePayload) -> None:
        """Handle a deploy safe payload."""
        sender = payload.sender

        if sender not in self.state.participants:
            # sender not in the set of participants.
            return

        if sender != self.state.safe_sender_address:
            # the sender is not the elected sender
            return

        if self._contract_address is not None:
            # contract address already set
            return

        self._contract_address = payload.safe_contract_address

    def check_deploy_safe(self, payload: DeploySafePayload) -> bool:
        """
        Check a deploy safe payload can be applied to the current state.

        A deploy safe transaction can be applied only if:
        - the sender belongs to the set of participants
        - the sender is the elected sender
        - the sender has not already sent its

        :param: payload: the payload.
        :return: True if the observation tx is allowed, False otherwise.
        """
        sender_in_participant_set = payload.sender in self.state.participants
        sender_is_elected_sender = payload.sender == self.state.safe_sender_address
        contract_address_not_set_yet = self._contract_address is None
        return (
            sender_in_participant_set
            and sender_is_elected_sender
            and contract_address_not_set_yet
        )

    @property
    def contract_set(self) -> bool:
        """Check that the contract has been set."""
        return self._contract_address is not None

    def end_block(self) -> Optional[Tuple[PeriodState, Optional["AbstractRound"]]]:
        """Process the end of the block."""
        # if reached participant threshold, set the result
        if self.contract_set:
            state = self.state.update(safe_contract_address=self._contract_address)
            next_round = CollectObservationRound(state, self._consensus_params)
            return state, next_round
        return None


class CollectObservationRound(BaseRound):
    """
    This class represents the 'collect-observation' round.

    Input: a period state with the set of participants
    Ouptut: a new period state with the set of participants and the observations

    It schedules the EstimateConsensusRound.
    """

    round_id = "collect_observation"

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the 'collect-observation' round."""
        super().__init__(*args, **kwargs)
        self.participant_to_observations: Dict[str, ObservationPayload] = {}

    def observation(self, payload: ObservationPayload) -> None:
        """Handle an 'observation' payload."""
        sender = payload.sender
        if sender not in self.state.participants:
            # sender not in the set of participants.
            return

        if sender in self.participant_to_observations:
            # sender has already sent its observation
            return

        self.participant_to_observations[sender] = payload

    def check_observation(self, payload: ObservationPayload) -> bool:
        """
        Check an observation payload can be applied to the current state.

        An observation transaction can be applied only if:
        - the sender belongs to the set of participants
        - the sender has not already sent its observation

        :param: payload: the payload.
        :return: True if the observation tx is allowed, False otherwise.
        """
        sender_in_participant_set = payload.sender in self.state.participants
        sender_has_not_sent_observation_yet = (
            payload.sender not in self.participant_to_observations
        )
        return sender_in_participant_set and sender_has_not_sent_observation_yet

    @property
    def observation_threshold_reached(self) -> bool:
        """Check that the observation threshold has been reached."""
        return (
            len(self.participant_to_observations)
            >= self._consensus_params.two_thirds_threshold
        )

    def end_block(self) -> Optional[Tuple[PeriodState, Optional["AbstractRound"]]]:
        """Process the end of the block."""
        # if reached observation threshold, set the result
        if self.observation_threshold_reached:
            state = self.state.update(
                participant_to_observations=MappingProxyType(
                    self.participant_to_observations
                )
            )
            next_round = EstimateConsensusRound(state, self._consensus_params)
            return state, next_round
        return None


class EstimateConsensusRound(BaseRound):
    """
    This class represents the 'estimate_consensus' round.

    Input: a period state with the set of participants and the observations
    Ouptut: a new period state with also the votes for each estimate
    """

    round_id = "estimate_consensus"

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the 'estimate consensus' round."""
        super().__init__(*args, **kwargs)
        self.participant_to_estimate: Dict[str, EstimatePayload] = {}

    def estimate(self, payload: EstimatePayload) -> None:
        """Handle an 'estimate' payload."""
        sender = payload.sender
        if sender not in self.state.participants:
            # sender not in the set of participants.
            return

        if sender in self.participant_to_estimate:
            # sender has already sent its estimate
            return

        self.participant_to_estimate[sender] = payload

    def check_estimate(self, payload: EstimatePayload) -> bool:
        """
        Check an estimate payload can be applied to the current state.

        An estimate transaction can be applied only if:
        - the round is in the 'estimate_consensus' state;
        - the sender belongs to the set of participants
        - the sender has not sent its estimate yet

        :param: payload: the payload.
        :return: True if the estimate tx is allowed, False otherwise.
        """
        sender_in_participant_set = payload.sender in self.state.participants
        sender_has_not_sent_estimate_yet = (
            payload.sender not in self.participant_to_estimate
        )
        return sender_in_participant_set and sender_has_not_sent_estimate_yet

    @property
    def estimate_threshold_reached(self) -> bool:
        """Check that the estimate threshold has been reached."""
        estimates_counter: CounterType = Counter()
        estimates_counter.update(
            payload.estimate for payload in self.participant_to_estimate.values()
        )
        # check that a single estimate has at least 2/3 of votes
        two_thirds_n = self._consensus_params.two_thirds_threshold
        return any(count >= two_thirds_n for count in estimates_counter.values())

    @property
    def most_voted_estimate(self) -> float:
        """Get the most voted estimate."""
        estimates_counter = Counter()  # type: ignore
        estimates_counter.update(
            payload.estimate for payload in self.participant_to_estimate.values()
        )
        most_voted_estimate, max_votes = max(
            estimates_counter.items(), key=itemgetter(1)
        )
        if max_votes < self._consensus_params.two_thirds_threshold:
            raise ValueError("estimate has not enough votes")
        return most_voted_estimate

    def end_block(self) -> Optional[Tuple[PeriodState, Optional["AbstractRound"]]]:
        """Process the end of the block."""
        if self.estimate_threshold_reached:
            state = self.state.update(
                participant_to_estimate=MappingProxyType(self.participant_to_estimate),
                most_voted_estimate=self.most_voted_estimate,
            )
            next_round = CollectSignatureRound(state, self._consensus_params)
            return state, next_round
        return None


class CollectSignatureRound(BaseRound):
    """This class represents the 'collect-signature' round."""

    round_id = "collect_signature"

    def __init__(self, *args: Any, **kwargs: Any):
        """Initialize the 'collect-signature' round."""
        super().__init__(*args, **kwargs)
        self.signatures_by_participant: Dict[str, str] = {}

    def signature(self, payload: SignaturePayload) -> None:
        """Handle a 'signature' payload."""
        sender = payload.sender
        if sender not in self.state.participants:
            # sender not in the set of participants.
            return

        if sender in self.signatures_by_participant:
            # sender has already sent its signature
            return

        self.signatures_by_participant[sender] = payload.signature

    def check_signature(self, payload: EstimatePayload) -> bool:
        """
        Check a signature payload can be applied to the current state.

        A signature transaction can be applied only if:
        - the round is in the 'collect-signature' state;
        - the sender belongs to the set of participants
        - the sender has not sent its signature yet

        :param: payload: the payload.
        :return: True if the signature tx is allowed, False otherwise.
        """
        sender_in_participant_set = payload.sender in self.state.participants
        sender_has_not_sent_signature_yet = (
            payload.sender not in self.signatures_by_participant
        )
        return sender_in_participant_set and sender_has_not_sent_signature_yet

    @property
    def signature_threshold_reached(self) -> bool:
        """Check that the signature threshold has been reached."""
        two_thirds_n = self._consensus_params.two_thirds_threshold
        return len(self.signatures_by_participant) >= two_thirds_n

    def end_block(self) -> Optional[Tuple[PeriodState, Optional["AbstractRound"]]]:
        """Process the end of the block."""
        if self.signature_threshold_reached:
            state = self.state.update(
                participant_to_signature=MappingProxyType(
                    self.signatures_by_participant
                )
            )
            next_round = ConsensusReachedRound(state, self._consensus_params)
            return state, next_round
        return None


class ConsensusReachedRound(BaseRound):
    """
    This class represents the 'consensus-reached' round.

    This round does not change the estimate on which the consensus was reached,
    i.e. the most voted estimate whose number of votes for the first time at the
    end of a block was above the 2/3 threshold. However, it still collects the
    remaining votes, if any.
    """

    round_id = "consensus_reached"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize a 'consensus-reached' round."""
        super().__init__(*args, **kwargs)
        self.final_participant_to_estimate: Dict[str, EstimatePayload] = {}

    def estimate(self, payload: EstimatePayload) -> None:
        """Handle an 'estimate' payload."""
        sender = payload.sender
        if sender not in self.state.participants:
            # sender not in the set of participants.
            return

        if sender in self.state.participant_to_estimate:
            # sender has already sent its estimate
            return

        self.final_participant_to_estimate[sender] = payload

    def check_estimate(self, payload: EstimatePayload) -> bool:
        """Check an estimate payload can be applied to the current state."""
        sender_in_participant_set = payload.sender in self.state.participants
        sender_has_not_sent_estimate_yet = (
            payload.sender not in self.state.participant_to_estimate
        )
        return sender_in_participant_set and sender_has_not_sent_estimate_yet

    def end_block(self) -> Optional[Tuple[PeriodState, Optional["AbstractRound"]]]:
        """Process the end of the block."""
        return None
