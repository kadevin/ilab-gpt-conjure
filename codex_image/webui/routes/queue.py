from __future__ import annotations

import asyncio
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse

from codex_image.webui.context import WebUIContext
from codex_image.webui.events import event_key, event_snapshot, queue_event, queue_snapshot, queued_or_running_task_ids, sse_message, task_events

EVENT_STREAM_CHECK_INTERVAL_SECONDS = 1.0


def register_queue_routes(app: FastAPI, ctx: WebUIContext) -> None:
    h = ctx.route_helpers

    @app.get("/api/queue")
    async def get_queue() -> dict[str, Any]:
        h["ensure_queue_worker_running"]()
        return queue_snapshot(ctx)

    @app.get("/api/events", response_model=None)
    async def events(request: Request, stream: bool = False) -> StreamingResponse:
        h["ensure_queue_worker_running"]()
        should_stream = stream

        async def stream_events():
            h["ensure_queue_worker_running"]()
            snapshot = event_snapshot(ctx)
            yield sse_message(snapshot)
            if not should_stream:
                return

            previous_queue = snapshot["queue"]
            previous_queue_key = event_key(previous_queue)
            previous_task_ids = queued_or_running_task_ids(previous_queue)
            while True:
                await asyncio.sleep(EVENT_STREAM_CHECK_INTERVAL_SECONDS)
                if await request.is_disconnected():
                    return
                h["ensure_queue_worker_running"]()
                queue = queue_snapshot(ctx)
                queue_key = event_key(queue)
                if queue_key == previous_queue_key:
                    continue

                current_task_ids = queued_or_running_task_ids(queue)
                finished_events = task_events(ctx, previous_task_ids - current_task_ids)
                yield sse_message(queue_event(queue, finished_events))
                for task_payload in finished_events:
                    yield sse_message(task_payload)
                previous_queue_key = queue_key
                previous_task_ids = current_task_ids

        return StreamingResponse(stream_events(), media_type="text/event-stream")

    @app.patch("/api/queue/reorder")
    def reorder_queue(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        task_ids = [str(item) for item in payload.get("task_ids", [])]
        try:
            ctx.queue_storage.reorder(task_ids)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return queue_snapshot(ctx)

    @app.post("/api/queue/{task_id}/promote")
    def promote_queue_task(task_id: str) -> dict[str, Any]:
        try:
            ctx.queue_storage.promote(task_id)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return queue_snapshot(ctx)

    @app.delete("/api/queue/{task_id}")
    async def delete_queue_task(task_id: str) -> dict[str, Any]:
        state = ctx.queue_storage.read_state()
        if task_id in state["waiting"]:
            ctx.queue_storage.remove_waiting(task_id)
            ctx.storage.delete_task(task_id)
            return {"ok": True, "task_id": task_id, "cancelled": False}
        running_channel_id = h["running_channel_for_task"](task_id)
        if running_channel_id is None:
            raise HTTPException(status_code=409, detail="Only waiting or running tasks can be cancelled from queue")
        try:
            h["mark_task_cancelled"](task_id)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        ctx.queue_storage.clear_running(running_channel_id)
        ctx.active_task_ids.discard(task_id)
        worker_task = ctx.running_worker_tasks.get(task_id)
        if worker_task is not None and not worker_task.done():
            worker_task.cancel()
            await asyncio.sleep(0)
        return {"ok": True, "task_id": task_id, "cancelled": True}
