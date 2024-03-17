"""Group for Zigbee Home Automation."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING, Any, NamedTuple

import zigpy.exceptions
from zigpy.types.named import EUI64

from zha.application.platforms import PlatformEntity, PlatformEntityStateChangedEvent
from zha.const import STATE_CHANGED
from zha.mixins import LogMixin

if TYPE_CHECKING:
    from zigpy.group import Group as ZigpyGroup, GroupEndpoint

    from zha.application.gateway import ZHAGateway
    from zha.application.platforms import GroupEntity
    from zha.zigbee.device import Device

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, kw_only=True)
class GroupMemberReference(NamedTuple):
    """Describes a group member."""

    ieee: EUI64
    endpoint_id: int


class GroupEntityReference(NamedTuple):
    """Reference to a group entity."""

    name: str | None
    original_name: str | None
    entity_id: int


class GroupMember(LogMixin):
    """Composite object that represents a device endpoint in a Zigbee group."""

    def __init__(self, zha_group: Group, device: Device, endpoint_id: int) -> None:
        """Initialize the group member."""
        self._group: Group = zha_group
        self._device: Device = device
        self._endpoint_id: int = endpoint_id

    @property
    def group(self) -> Group:
        """Return the group this member belongs to."""
        return self._group

    @property
    def endpoint_id(self) -> int:
        """Return the endpoint id for this group member."""
        return self._endpoint_id

    @property
    def endpoint(self) -> GroupEndpoint:
        """Return the endpoint for this group member."""
        return self._device.device.endpoints.get(self.endpoint_id)

    @property
    def device(self) -> Device:
        """Return the ZHA device for this group member."""
        return self._device

    @property
    def member_info(self) -> dict[str, Any]:
        """Get ZHA group info."""
        member_info: dict[str, Any] = {}
        member_info["endpoint_id"] = self.endpoint_id
        member_info["device"] = self.device.zha_device_info
        member_info["entities"] = self.associated_entities
        return member_info

    # pylint: disable=pointless-string-statement
    """ TODO verify
    @property
    def associated_entities(self) -> list[dict[str, Any]]:
        #Return the list of entities that were derived from this endpoint.
        entity_registry = er.async_get(self._device.hass)
        zha_device_registry = self.device.gateway.device_registry

        entity_info = []

        for entity_ref in zha_device_registry.get(self.device.ieee):
            # We have device entities now that don't leverage cluster handlers
            if not entity_ref.cluster_handlers:
                continue
            entity = entity_registry.async_get(entity_ref.reference_id)
            handler = list(entity_ref.cluster_handlers.values())[0]

            if (
                entity is None
                or handler.cluster.endpoint.endpoint_id != self.endpoint_id
            ):
                continue

            entity_info.append(
                GroupEntityReference(
                    name=entity.name,
                    original_name=entity.original_name,
                    entity_id=entity_ref.reference_id,
                )._asdict()
            )

        return entity_info
        """

    @property
    def associated_entities(self) -> list[PlatformEntity]:
        """Return the list of entities that were derived from this endpoint."""
        return [
            platform_entity
            for platform_entity in self._device.platform_entities.values()
            if platform_entity.endpoint.id == self.endpoint_id
        ]

    async def async_remove_from_group(self) -> None:
        """Remove the device endpoint from the provided zigbee group."""
        try:
            await self._device.device.endpoints[self._endpoint_id].remove_from_group(
                self._group.group_id
            )
        except (zigpy.exceptions.ZigbeeException, TimeoutError) as ex:
            self.debug(
                (
                    "Failed to remove endpoint: %s for device '%s' from group: 0x%04x"
                    " ex: %s"
                ),
                self._endpoint_id,
                self._device.ieee,
                self._group.group_id,
                str(ex),
            )

    def log(self, level: int, msg: str, *args: Any, **kwargs) -> None:
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (f"0x{self._group.group_id:04x}", self.endpoint_id) + args
        _LOGGER.log(level, msg, *args, **kwargs)


class Group(LogMixin):
    """ZHA Zigbee group object."""

    def __init__(
        self,
        gateway: ZHAGateway,
        zigpy_group: zigpy.group.Group,
    ) -> None:
        """Initialize the group."""
        self._gateway = gateway
        self._zigpy_group = zigpy_group
        self._group_entities: dict[str, GroupEntity] = {}
        self._entity_unsubs: dict[str, Callable] = {}

    @property
    def name(self) -> str:
        """Return group name."""
        return self._zigpy_group.name

    @property
    def group_id(self) -> int:
        """Return group name."""
        return self._zigpy_group.group_id

    @property
    def endpoint(self) -> zigpy.endpoint.Endpoint:
        """Return the endpoint for this group."""
        return self._zigpy_group.endpoint

    @property
    def group_entities(self) -> dict[str, GroupEntity]:
        """Return the platform entities of the group."""
        return self._group_entities

    @property
    def zigpy_group(self) -> ZigpyGroup:
        """Return the zigpy group."""
        return self._zigpy_group

    @property
    def gateway(self) -> ZHAGateway:
        """Return the gateway for this group."""
        return self._gateway

    @property
    def members(self) -> list[GroupMember]:
        """Return the ZHA devices that are members of this group."""
        return [
            GroupMember(self, self._gateway.devices[member_ieee], endpoint_id)
            for (member_ieee, endpoint_id) in self._zigpy_group.members
            if member_ieee in self._gateway.devices
        ]

    # pylint: disable=pointless-string-statement
    """ TODO verify
    async def async_add_members(self, members: list[GroupMemberReference]) -> None:
        #Add members to this group.
        if len(members) > 1:
            tasks = []
            for member in members:
                tasks.append(
                    self._gateway.devices[member.ieee].async_add_endpoint_to_group(
                        member.endpoint_id, self.group_id
                    )
                )
            await asyncio.gather(*tasks)
        else:
            await self._gateway.devices[members[0].ieee].async_add_endpoint_to_group(
                members[0].endpoint_id, self.group_id
            )

    async def async_remove_members(self, members: list[GroupMemberReference]) -> None:
        #Remove members from this group.
        if len(members) > 1:
            tasks = []
            for member in members:
                tasks.append(
                    self._gateway.devices[member.ieee].async_remove_endpoint_from_group(
                        member.endpoint_id, self.group_id
                    )
                )
            await asyncio.gather(*tasks)
        else:
            await self._gateway.devices[
                members[0].ieee
            ].async_remove_endpoint_from_group(members[0].endpoint_id, self.group_id)
    """

    def register_group_entity(self, group_entity: GroupEntity) -> None:
        """Register a group entity."""
        if group_entity.unique_id not in self._group_entities:
            self._group_entities[group_entity.unique_id] = group_entity
            self._entity_unsubs[group_entity.unique_id] = group_entity.on_event(
                STATE_CHANGED,
                self._maybe_update_group_members,
            )
        self.update_entity_subscriptions()

    @property
    def member_entity_ids(self) -> list[str]:
        """Return the ZHA entity ids for all entities for the members of this group."""
        all_entity_ids: list[str] = []
        for member in self.members:
            entity_references = member.associated_entities
            for entity_reference in entity_references:
                all_entity_ids.append(entity_reference["entity_id"])
        return all_entity_ids

    # pylint: disable=pointless-string-statement
    """ TODO verify
    def get_domain_entity_ids(self, domain: str) -> list[str]:
        #Return entity ids from the entity domain for this group.
        entity_registry = er.async_get(self.hass)
        domain_entity_ids: list[str] = []

        for member in self.members:
            if member.device.is_coordinator:
                continue
            entities = async_entries_for_device(
                entity_registry,
                member.device.device_id,
                include_disabled_entities=True,
            )
            domain_entity_ids.extend(
                [entity.entity_id for entity in entities if entity.domain == domain]
            )
        return domain_entity_ids
    """

    @property
    def group_info(self) -> dict[str, Any]:
        """Get ZHA group info."""
        group_info: dict[str, Any] = {}
        group_info["group_id"] = self.group_id
        group_info["name"] = self.name
        group_info["members"] = [member.member_info for member in self.members]
        return group_info

    def send_event(self, event: dict[str, Any]) -> None:
        """Send an event from this group."""
        # TODO self._server.client_manager.broadcast(event) #pylint: disable=fixme

    async def _maybe_update_group_members(
        self, event: PlatformEntityStateChangedEvent
    ) -> None:
        """Update the state of the entities that make up the group if they are marked as should poll."""
        tasks = []
        platform_entities = self.get_platform_entities(event.platform)
        for platform_entity in platform_entities:
            if platform_entity.should_poll:
                tasks.append(platform_entity.async_update())
        if tasks:
            await asyncio.gather(*tasks)

    def update_entity_subscriptions(self) -> None:
        """Update the entity event subscriptions.

        Loop over all the entities in the group and update the event subscriptions. Get all of the unique ids
        for both the group entities and the entities that they are compositions of. As we loop through the member
        entities we establish subscriptions for their events if they do not exist. We also add the entity unique id
        to a list for future processing. Once we have processed all group entities we combine the list of unique ids
        for group entities and the platrom entities that we processed. Then we loop over all of the unsub ids and we
        execute the unsubscribe method for each one that isn't in the combined list.
        """
        group_entity_ids = list(self._group_entities.keys())
        processed_platform_entity_ids = []
        for group_entity in self._group_entities.values():
            for platform_entity in self.get_platform_entities(group_entity.PLATFORM):
                processed_platform_entity_ids.append(platform_entity.unique_id)
                if platform_entity.unique_id not in self._entity_unsubs:
                    self._entity_unsubs[platform_entity.unique_id] = (
                        platform_entity.on_event(
                            STATE_CHANGED,
                            group_entity.update,
                        )
                    )
        all_ids = group_entity_ids + processed_platform_entity_ids
        existing_unsub_ids = self._entity_unsubs.keys()
        processed_unsubs = []
        for unsub_id in existing_unsub_ids:
            if unsub_id not in all_ids:
                self._entity_unsubs[unsub_id]()
                processed_unsubs.append(unsub_id)

        for unsub_id in processed_unsubs:
            self._entity_unsubs.pop(unsub_id)

    async def async_add_members(self, members: list[GroupMemberReference]) -> None:
        """Add members to this group."""
        # TODO handle entity change unsubs and sub for new events
        devices: dict[EUI64, Device] = self._gateway.devices
        if len(members) > 1:
            tasks = []
            for member in members:
                tasks.append(
                    devices[member.ieee].async_add_endpoint_to_group(
                        member.endpoint_id, self.group_id
                    )
                )
            await asyncio.gather(*tasks)
        else:
            member = members[0]
            await devices[member.ieee].async_add_endpoint_to_group(
                member.endpoint_id, self.group_id
            )
        self.update_entity_subscriptions()

    async def async_remove_members(self, members: list[GroupMemberReference]) -> None:
        """Remove members from this group."""
        # TODO handle entity change unsubs and sub for new events
        devices: dict[EUI64, Device] = self._gateway.devices
        if len(members) > 1:
            tasks = []
            for member in members:
                tasks.append(
                    devices[member.ieee].async_remove_endpoint_from_group(
                        member.endpoint_id, self.group_id
                    )
                )
            await asyncio.gather(*tasks)
        else:
            member = members[0]
            await devices[member.ieee].async_remove_endpoint_from_group(
                member.endpoint_id, self.group_id
            )
        self.update_entity_subscriptions()

    @property
    def all_member_entity_unique_ids(self) -> list[str]:
        """Return all platform entities unique ids for the members of this group."""
        all_entity_unique_ids: list[str] = []
        for member in self.members:
            entities = member.associated_entities
            for entity in entities:
                all_entity_unique_ids.append(entity.unique_id)
        return all_entity_unique_ids

    def get_platform_entities(self, platform: str) -> list[PlatformEntity]:
        """Return entities belonging to the specified platform for this group."""
        platform_entities: list[PlatformEntity] = []
        for member in self.members:
            if member.device.is_coordinator:
                continue
            for entity in member.associated_entities:
                if platform == entity.PLATFORM:
                    platform_entities.append(entity)

        return platform_entities

    def to_json(self) -> dict[str, Any]:
        """Get ZHA group info."""
        group_info: dict[str, Any] = {}
        group_info["id"] = self.group_id
        group_info["name"] = self.name
        group_info["members"] = {
            str(member.device.ieee): member.to_json() for member in self.members
        }
        group_info["entities"] = {
            unique_id: entity.to_json()
            for unique_id, entity in self._group_entities.items()
        }
        return group_info

    def log(self, level: int, msg: str, *args: Any, **kwargs) -> None:
        """Log a message."""
        msg = f"[%s](%s): {msg}"
        args = (self.name, self.group_id) + args
        _LOGGER.log(level, msg, *args, **kwargs)
