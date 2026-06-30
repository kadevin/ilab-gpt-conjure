from __future__ import annotations

import json
from typing import Any, Iterable

from .context import WebUIContext
from .task_metadata import _gallery_item_response, _with_file_urls


def queue_snapshot(ctx: WebUIContext) -> dict[str, Any]:
    state = ctx.queue_storage.read_state()
    active_ids = ctx.route_helpers["visible_running_task_ids"]()
    waiting = [
        _with_file_urls(task, active_ids, ctx.gallery_storage, ctx.reference_asset_storage, include_request=False)
        for task in (ctx.storage.read_metadata(task_id) for task_id in state["waiting"] if ctx.storage.metadata_path(task_id).exists())
    ]
    running = []
    for channel_id, item in state["running"].items():
        metadata_path = ctx.storage.metadata_path(str(item.get("task_id") or "")) if isinstance(item, dict) else None
        if metadata_path is None or not metadata_path.exists():
            continue
        task = _with_file_urls(
            ctx.storage.read_metadata(str(item["task_id"])),
            active_ids,
            ctx.gallery_storage,
            ctx.reference_asset_storage,
            include_request=False,
        )
        task["channel_id"] = channel_id
        task["account_id"] = item.get("account_id")
        running.append(task)
    channels = ctx.queue_manager.channels if ctx.queue_manager is not None else []
    queue_channel_available = ctx.route_helpers["queue_channel_available"]
    return {
        "waiting": waiting,
        "running": running,
        "summary": {
            "waiting_count": len(waiting),
            "running_count": len(running),
            "channel_count": len(channels),
            "usable_channel_count": sum(1 for channel in channels if queue_channel_available(channel)),
        },
    }


def event_snapshot(ctx: WebUIContext) -> dict[str, Any]:
    return {
        "type": "snapshot",
        "tasks": ctx.storage.list_recent_task_cards(limit=200),
        "queue": queue_snapshot(ctx),
        "gallery": [_gallery_item_response(item) for item in ctx.gallery_storage.list_items()],
        "auth": ctx.route_helpers["auth_event_payload"](),
    }


def sse_message(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def event_key(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def queued_or_running_task_ids(queue: dict[str, Any]) -> set[str]:
    return {
        str(task.get("task_id"))
        for task in list(queue.get("waiting") or []) + list(queue.get("running") or [])
        if isinstance(task, dict) and task.get("task_id")
    }


def task_event(ctx: WebUIContext, task_id: str) -> dict[str, Any] | None:
    if not ctx.storage.metadata_path(task_id).exists():
        return None
    return {
        "type": "task",
        "task": _with_file_urls(
            ctx.storage.read_metadata(task_id),
            ctx.route_helpers["visible_running_task_ids"](),
            ctx.gallery_storage,
            ctx.reference_asset_storage,
            include_request=False,
        ),
    }


def task_events(ctx: WebUIContext, task_ids: Iterable[str]) -> list[dict[str, Any]]:
    events = []
    for task_id in sorted({str(task_id) for task_id in task_ids if str(task_id or "")}):
        payload = task_event(ctx, task_id)
        if payload is not None:
            events.append(payload)
    return events


def queue_event(queue: dict[str, Any], finished_task_events: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"type": "queue", "queue": queue}
    finished_tasks = [
        event.get("task")
        for event in (finished_task_events or [])
        if isinstance(event, dict) and isinstance(event.get("task"), dict)
    ]
    if finished_tasks:
        payload["tasks"] = finished_tasks
    return payload
