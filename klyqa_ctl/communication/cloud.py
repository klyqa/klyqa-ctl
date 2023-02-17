"""Cloud connection handling"""
from __future__ import annotations

import argparse
import asyncio
from asyncio import AbstractEventLoop, CancelledError, Task
from collections import ChainMap
import datetime
from enum import Enum
import json
import traceback
from typing import Any
import uuid

import httpx

from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.device import Device
from klyqa_ctl.general.general import (
    LOGGER,
    PROD_HOST,
    DeviceConfig,
    EventQueuePrinter,
    TypeJson,
    async_json_cache,
    format_uid,
    get_asyncio_loop,
    task_log_debug,
    task_log_trace,
    task_log_trace_ex,
)

DEFAULT_HTTP_REQUEST_TIMEOUT_SECS: int = 30


class RequestMethod(str, Enum):
    """HTTP request methods."""

    POST = "POST"
    GET = "GET"


class CloudBackend:
    """Cloud backend control."""

    def __init__(self, controller_data: ControllerData) -> None:
        self._attr_controller_data: ControllerData = controller_data
        self._attr_offline: bool = False
        self._attr_host: str = PROD_HOST

    @property
    def host(self) -> str:
        """Return or set the host."""
        return self._attr_host

    @host.setter
    def host(self, host: str) -> None:
        self._attr_host = host

    @property
    def offline(self) -> bool:
        """Return or set the offline attribute."""
        return self._attr_offline

    @property
    def controller_data(self) -> ControllerData:
        """Return or set the controller data object."""
        return self._attr_controller_data

    def backend_connected(self) -> bool:
        """General cloud intended to be there check."""
        return not self.offline and self.host != ""

    async def get_device_config(
        self, product_id: str, device_configs: TypeJson
    ) -> None:
        """Request device config from the cloud."""
        task_log_debug(
            f"Try request device config for {product_id} from server."
        )
        try:
            config: TypeJson | None = None
            config_http: httpx.Response | None = await self.request(
                RequestMethod.GET,
                "config/product/" + product_id,
                timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECS,
            )
            if config_http:
                config = await self.load_http_response(config_http)
        except asyncio.TimeoutError:
            LOGGER.error("Timed out get device config http request!")
            return None
        if config:
            device_configs[product_id] = DeviceConfig(config)
        return None

    async def get_device_configs(self, device_product_ids: set[str]) -> None:
        """Request device configs by product id from the cloud."""

        if device_product_ids and self.controller_data.device_configs:
            device_tasks: list[Task] = [
                asyncio.create_task(
                    self.get_device_config(
                        product_id, self.controller_data.device_configs
                    )
                )
                for product_id in device_product_ids
            ]
            await asyncio.wait(
                device_tasks, timeout=DEFAULT_HTTP_REQUEST_TIMEOUT_SECS
            )

        device_configs_cache, cached = await async_json_cache(
            self.controller_data.device_configs, "device.configs.json"
        )
        if cached and device_configs_cache:
            self.controller_data.device_configs = device_configs_cache
            LOGGER.info("No server reply for device configs. Using cache.")
        return None

    async def update_devices_configs(
        self, device_product_ids: set[str]
    ) -> None:
        """Update the device configs of all added devices."""

        dev: Device
        await self.get_device_configs(device_product_ids)

        for _, dev in self.controller_data.devices.items():
            dev.read_device_config(
                device_config=self.controller_data.device_configs[
                    dev.product_id
                ]
            )

    async def update_devices_configs_all(self) -> None:
        """Update the device configs of all added devices."""

        await self.update_devices_configs(
            set(
                [
                    dev.product_id
                    for _, dev in self.controller_data.devices.items()
                ]
            )
        )

    def get_header_default(self) -> TypeJson:
        """Get default request header for cloud request."""

        header: dict[str, str] = {
            "X-Request-Id": str(uuid.uuid4()),
            "Accept": "application/json",
            "Content-Type": "application/json",
            "accept-encoding": "gzip, deflate, utf-8",
        }
        return header

    async def request(
        self,
        method: RequestMethod,
        url: str,
        headers: TypeJson | None = None,
        **kwargs: Any,
    ) -> httpx.Response | None:
        """Send http request with request method to url with headers."""

        response: httpx.Response | None = None
        try:
            url_full: str = self.host + "/" + url
            kw_str: str = ", ".join(
                f"{key}={value}" for key, value in kwargs.items()
            )
            header: TypeJson = (
                headers if headers else self.get_header_default()
            )
            task_log_debug("Send cloud request to %s.", url_full)
            task_log_trace(
                "Send cloud request to %s: %s, %s", url_full, header, kw_str
            )
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method.value,
                    url=url_full,
                    headers=header,
                    **kwargs,
                )

        except EnvironmentError:
            LOGGER.error(
                "Environment error occured during send request to cloud"
                " backend!"
            )
            task_log_trace_ex()
        except httpx.HTTPError:
            LOGGER.error(
                "Connection error occured during send request to cloud"
                " backend!"
            )
            task_log_trace_ex()
        return response

    async def load_http_response(
        self, response: httpx.Response
    ) -> TypeJson | None:
        """Load http response into json object."""

        answer: TypeJson | None = None
        if not response:
            LOGGER.error("No response from cloud request.")
            return None

        if int(str(response.status_code)[0]) not in [
            1,
            2,
            3,
        ]:
            LOGGER.error("Invalid response from cloud request.")
            return None

        try:
            answer = json.loads(response.text)
        except json.JSONDecodeError as err:
            LOGGER.error(err.msg)
            task_log_debug(f"{traceback.format_exc()} {err.msg}")
            answer = None
        return answer

    # async def cloud_send_command(self, command: Command) -> Message:
    #     msg: Message = Message(
    #         datetime.datetime.now(),

    #     )

    async def send(
        self,
        args: argparse.Namespace,
        target_device_uids: set[str],
        to_send_device_uids: set[
            str
        ],  # the device unit ids remaining to send from --tryLocalThanCloud
        timeout_ms: int,
        message_queue_tx_state_cloud: list,
        message_queue_tx_command_cloud: list,
    ) -> bool:
        """Cloud message processing."""

        queue_printer: EventQueuePrinter = EventQueuePrinter()
        response_queue: list[Any] = []

        success: bool = False

        async def _cloud_post(
            device: Device, json_message: TypeJson, target: str
        ) -> None:
            # TODO: distinguish between standalone devicesettings like
            # cloudDeviceId and localDeviceId, and account settings per account
            cloud_device_id: str = device.acc_sets["cloudDeviceId"]
            unit_id: str = format_uid(device.acc_sets["localDeviceId"])
            LOGGER.info(
                "Post {target} to the device '%s' (unit_id:"
                " %s) over the cloud.",
                cloud_device_id,
                unit_id,
            )
            response: TypeJson = {
                cloud_device_id: await self.request(
                    RequestMethod.POST,
                    url=f"device/{cloud_device_id}/{target}",
                    json=json_message,
                )
            }
            resp_print: str = ""
            name: str = device.u_id
            if device.acc_sets and "name" in device.acc_sets:
                name = device.acc_sets["name"]
            resp_print = f'Device "{name}" cloud response:'
            resp_print = json.dumps(response, sort_keys=True, indent=4)
            device.cloud.received_packages.append(response)
            response_queue.append(resp_print)
            queue_printer.print(resp_print)

        async def cloud_post(
            device: Device, json_message: TypeJson, target: str
        ) -> int:
            if not await device.use_lock():
                LOGGER.error(
                    "Couldn't get use lock for device %s)", device.get_name()
                )
                return 1
            try:
                await _cloud_post(device, json_message, target)
            except CancelledError:
                LOGGER.error(
                    "Cancelled cloud send %s.",
                    device.u_id if device.u_id else "",
                )
            finally:
                device.use_unlock()
            return 0

        started: datetime.datetime = datetime.datetime.now()
        # timeout_ms = 30000

        async def process_cloud_messages(target_uids: set[str]) -> None:

            loop: AbstractEventLoop = get_asyncio_loop()
            threads: list[Any] = []
            target_devices: list[Device] = [
                b
                for b in self.controller_data.devices.values()
                for t in target_uids
                if b.u_id == t
            ]

            def create_post_threads(
                target: str, msg: TypeJson
            ) -> list[tuple[Task[int], Device]]:
                return [
                    (loop.create_task(cloud_post(b, msg, target)), b)
                    for b in target_devices
                ]

            state_payload_message = dict(
                ChainMap(*message_queue_tx_state_cloud)
            )
            # state_payload_message = (
            #     json.loads(*message_queue_tx_state_cloud)
            #     if message_queue_tx_state_cloud
            #     else ""
            # )

            command_payload_message = dict(
                ChainMap(*message_queue_tx_command_cloud)
            )
            # command_payload_message = (
            #     json.loads(*message_queue_tx_command_cloud)
            #     if message_queue_tx_command_cloud
            #     else ""
            # )
            if state_payload_message:
                threads.extend(
                    create_post_threads(
                        "state", {"payload": state_payload_message}
                    )
                )
            if command_payload_message:
                threads.extend(
                    create_post_threads("command", command_payload_message)
                )

            count: int = 0
            timeout: float = timeout_ms / 1000
            for worker, device in threads:
                count = count + 1
                # wait at most timeout_ms wanted minus seconds elapsed since
                # sending
                try:
                    await asyncio.wait_for(
                        worker,
                        timeout=timeout
                        - (datetime.datetime.now() - started).seconds,
                    )
                except asyncio.TimeoutError:
                    LOGGER.error('Timeout for "%s""!', device.get_name())
                    worker.cancel()
                except Exception:
                    task_log_trace_ex()

        await process_cloud_messages(
            target_device_uids if args.cloud else to_send_device_uids
        )
        # if there are still target devices that the local send couldn't
        # reach, try send the to_send_device_uids via cloud

        queue_printer.stop()

        if response_queue:
            success = True
        return success

    @classmethod
    def create_default(
        cls: Any, controller_data: ControllerData, host: str = PROD_HOST
    ) -> CloudBackend:
        """Factory for cloud backend."""
        cloud: CloudBackend = CloudBackend(controller_data=controller_data)
        cloud.host = host
        return cloud
