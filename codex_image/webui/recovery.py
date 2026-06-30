from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from .storage import QueueStorage, TaskStorage, utc_now
from .task_enrichment import _dedupe_preserve_order, _input_sources, _input_urls
from .task_outputs import _output_url, _positive_int


def _migrate_legacy_task_directories(storage: TaskStorage, legacy_roots: list[Path]) -> None:
    seen: set[Path] = set()
    for legacy_root in legacy_roots:
        root = legacy_root.expanduser()
        resolved = root.resolve(strict=False)
        if resolved in seen:
            continue
        seen.add(resolved)
        if not root.exists() or not root.is_dir():
            continue
        for metadata_path in sorted(root.glob("*/metadata.json")):
            task_dir = metadata_path.parent
            task_id = task_dir.name
            try:
                target_metadata_path = storage.metadata_path(task_id)
            except ValueError:
                continue
            if target_metadata_path.exists():
                continue
            try:
                metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(metadata, dict):
                continue
            migrated_inputs = _migrate_legacy_inputs(storage, task_id, task_dir, metadata)
            migrated_mask = _migrate_legacy_mask(storage, task_id, task_dir, metadata)
            migrated_outputs = _migrate_legacy_outputs(storage, task_id, task_dir, metadata)
            metadata["task_id"] = task_id
            metadata["input_files"] = [path.name for path in migrated_inputs]
            metadata["input_urls"] = _input_urls(task_id, metadata["input_files"])
            if migrated_mask is not None:
                metadata["mask_file"] = migrated_mask.name
            if migrated_outputs:
                metadata["output_files"] = [storage.output_file(path) for path in migrated_outputs]
                metadata["output_urls"] = [_output_url(storage, path) for path in migrated_outputs]
                metadata["output_file"] = storage.output_file(migrated_outputs[0])
                metadata["output_url"] = _output_url(storage, migrated_outputs[0])
            raw_gallery_refs = metadata.get("gallery_refs")
            gallery_refs = [dict(ref) for ref in raw_gallery_refs if isinstance(ref, dict)] if isinstance(raw_gallery_refs, list) else []
            if gallery_refs:
                metadata["input_sources"] = _input_sources(task_id, metadata["input_files"], gallery_refs)
            storage.write_metadata(task_id, metadata)
            request_path = task_dir / "request.json"
            if request_path.exists():
                storage.request_path(task_id).write_bytes(request_path.read_bytes())
            debug_path = task_dir / "debug-sse.jsonl"
            if debug_path.exists():
                storage.debug_sse_path(task_id).write_bytes(debug_path.read_bytes())
            try:
                shutil.rmtree(task_dir)
            except OSError:
                continue


def _migrate_legacy_inputs(storage: TaskStorage, task_id: str, task_dir: Path, metadata: dict[str, Any]) -> list[Path]:
    input_dir = task_dir / "inputs"
    input_names = [str(name) for name in metadata.get("input_files", []) if isinstance(name, str)]
    migrated: list[Path] = []
    for index, name in enumerate(input_names, start=1):
        source = input_dir / Path(name).name
        if not source.exists():
            continue
        target = storage.write_input(task_id, source.name, source.read_bytes(), index=index)
        migrated.append(target)
    return migrated


def _migrate_legacy_mask(storage: TaskStorage, task_id: str, task_dir: Path, metadata: dict[str, Any]) -> Path | None:
    mask_name = metadata.get("mask_file")
    if not isinstance(mask_name, str) or not mask_name:
        return None
    source = task_dir / "inputs" / Path(mask_name).name
    if not source.exists():
        return None
    return storage.write_input(task_id, source.name, source.read_bytes(), kind="mask", index=1)


def _migrate_legacy_outputs(storage: TaskStorage, task_id: str, task_dir: Path, metadata: dict[str, Any]) -> list[Path]:
    names: list[str] = []
    output_files = metadata.get("output_files")
    if isinstance(output_files, list):
        names.extend(str(name) for name in output_files if isinstance(name, str))
    output_file = metadata.get("output_file")
    if isinstance(output_file, str) and output_file and output_file not in names:
        names.insert(0, output_file)
    migrated: list[Path] = []
    for index, name in enumerate(_dedupe_preserve_order(names), start=1):
        source = task_dir / Path(name).name
        if not source.exists():
            continue
        suffix = source.suffix.lstrip(".") or str((metadata.get("params") or {}).get("output_format") or "png")
        target = storage.write_output(task_id, source.read_bytes(), suffix, index=index)
        migrated.append(target)
    return migrated


def _migrate_legacy_gallery_directory(gallery_path: Path, legacy_roots: list[Path]) -> None:
    target_root = gallery_path.expanduser()
    target_resolved = target_root.resolve(strict=False)
    seen: set[Path] = set()
    for legacy_root in legacy_roots:
        root = legacy_root.expanduser()
        resolved = root.resolve(strict=False)
        if resolved in seen or resolved == target_resolved:
            continue
        seen.add(resolved)
        if not root.exists() or not root.is_dir():
            continue
        for metadata_path in sorted(root.glob("*/metadata.json")):
            item_dir = metadata_path.parent
            item_id = item_dir.name
            if not item_id or "/" in item_id or "\\" in item_id:
                continue
            target_dir = target_root / item_id
            if target_dir.exists():
                continue
            target_dir.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copytree(item_dir, target_dir)
            except OSError:
                continue
            try:
                shutil.rmtree(item_dir)
            except OSError:
                continue
        try:
            root.rmdir()
        except OSError:
            pass


def _prune_missing_queue_tasks(queue_storage: QueueStorage, storage: TaskStorage) -> None:
    state = queue_storage.read_state()
    waiting = [task_id for task_id in state["waiting"] if storage.metadata_path(task_id).exists()]
    running = {
        channel_id: entry
        for channel_id, entry in state["running"].items()
        if isinstance(entry, dict) and storage.metadata_path(str(entry.get("task_id") or "")).exists()
    }
    if waiting != state["waiting"] or running != state["running"]:
        state["waiting"] = waiting
        state["running"] = running
        queue_storage.write_state(state)


def _prune_duplicate_request_payloads(storage: TaskStorage) -> None:
    if not storage.source_data_root.exists():
        return
    for metadata_path in storage.iter_metadata_paths():
        task_id = metadata_path.name.removesuffix(".metadata.json")
        request_path = storage.request_path(task_id)
        if not request_path.exists():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(metadata, dict) or "request" not in metadata:
            continue
        metadata.pop("request", None)
        try:
            metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")
        except OSError:
            continue


def _materialize_orphaned_running_failure(
    storage: TaskStorage,
    task_id: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    if metadata.get("status") != "running":
        return metadata
    interrupted_at = utc_now()
    message = str(metadata.get("last_error") or metadata.get("error") or "Service restarted before this task completed.")
    output_records = metadata.get("outputs")
    normalized_outputs: list[Any] = []
    completed_count = 0
    failed_count = 0
    if isinstance(output_records, list):
        for raw_record in output_records:
            if not isinstance(raw_record, dict):
                normalized_outputs.append(raw_record)
                continue
            record = dict(raw_record)
            status = str(record.get("status") or "")
            if status in {"running", "queued", "waiting", ""}:
                record["status"] = "failed"
                record.setdefault("error", message)
            if record.get("status") == "completed":
                completed_count += 1
            elif record.get("status") == "failed":
                failed_count += 1
            normalized_outputs.append(record)
    total_count = _positive_int(metadata.get("total_count")) or _positive_int((metadata.get("params") or {}).get("n")) or 1
    failed_count += max(0, total_count - completed_count - failed_count)
    updated = dict(metadata)
    updated.update(
        {
            "status": "failed",
            "updated_at": interrupted_at,
            "error": message,
            "last_error": message,
            "generated_count": completed_count,
            "failed_count": failed_count,
        }
    )
    if isinstance(output_records, list):
        updated["outputs"] = normalized_outputs
    updated.pop("request", None)
    storage.write_metadata(task_id, updated)
    return updated


def _recover_queue_state(storage: TaskStorage, queue_storage: QueueStorage) -> None:
    state = queue_storage.read_state()
    queued_task_ids: list[str] = []
    for task in storage.rebuild_task_index():
        task_id = str(task.get("task_id") or "")
        status = str(task.get("status") or "")
        if status in {"queued", "running"} and _recover_completed_outputs_from_disk(storage, task):
            continue
        if status == "queued" and _is_legacy_auto_retry_queue_task(task):
            message = str(task.get("last_error") or task.get("error") or "Task stopped before manual retry.")
            task["status"] = "failed"
            task["updated_at"] = utc_now()
            task["error"] = message
            task["last_error"] = message
            storage.write_metadata(task_id, task)
            continue
        if status == "queued" and task_id:
            queued_task_ids.append(task_id)
        if status == "running" and task_id:
            task["status"] = "failed"
            task["updated_at"] = utc_now()
            task["error"] = "Service restarted before this task completed."
            task["last_error"] = task["error"]
            storage.write_metadata(task_id, task)
    queued_task_id_set = set(queued_task_ids)
    waiting = [task_id for task_id in state["waiting"] if task_id in queued_task_id_set]
    for task_id in queued_task_ids:
        if task_id not in waiting:
            waiting.append(task_id)
    state["waiting"] = _dedupe_preserve_order(waiting)
    state["running"] = {}
    queue_storage.write_state(state)


def _is_legacy_auto_retry_queue_task(task: dict[str, Any]) -> bool:
    if _positive_int(task.get("attempts")) is None:
        return False
    if task.get("retry_requested_at"):
        return False
    return bool(task.get("last_error") or task.get("error"))


def _recover_completed_outputs_from_disk(storage: TaskStorage, task: dict[str, Any]) -> bool:
    task_id = str(task.get("task_id") or "")
    if not task_id:
        return False
    output_paths = _disk_output_paths(storage, task_id)
    if not output_paths:
        return False
    total_count = _recoverable_total_count(task, len(output_paths))
    if total_count <= 0 or len(output_paths) < total_count:
        return False

    selected_paths = output_paths[:total_count]
    existing_outputs = {
        int(record["index"]): record
        for record in task.get("outputs", [])
        if isinstance(record, dict) and isinstance(record.get("index"), int)
    }
    outputs: list[dict[str, Any]] = []
    for path in selected_paths:
        index = _output_index_from_path(path) or len(outputs) + 1
        record = dict(existing_outputs.get(index) or {})
        record.update(
            {
                "index": index,
                "status": "completed",
                "file": storage.output_file(path),
                "url": _output_url(storage, path),
            }
        )
        outputs.append(record)

    output_files = [storage.output_file(path) for path in selected_paths]
    output_urls = [_output_url(storage, path) for path in selected_paths]
    params = task.get("params") if isinstance(task.get("params"), dict) else {}
    output_formats = [path.suffix.lstrip(".") or str(params.get("output_format") or "png") for path in selected_paths]
    output_size = task.get("output_size") or params.get("size")
    task.update(
        {
            "status": "completed",
            "updated_at": utc_now(),
            "generated_count": len(selected_paths),
            "failed_count": 0,
            "total_count": total_count,
            "output_file": output_files[0],
            "output_files": output_files,
            "output_url": output_urls[0],
            "output_urls": output_urls,
            "outputs": outputs,
            "output_format": output_formats[0],
            "output_formats": output_formats,
        }
    )
    if output_size:
        task["output_size"] = output_size
        task["output_sizes"] = [output_size for _ in selected_paths]
    task.pop("error", None)
    task.pop("last_error", None)
    storage.write_metadata(task_id, task)
    return True


def _recoverable_total_count(task: dict[str, Any], fallback: int) -> int:
    for value in (task.get("total_count"), (task.get("params") or {}).get("n") if isinstance(task.get("params"), dict) else None):
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            continue
        if parsed > 0:
            return parsed
    return fallback


def _disk_output_paths(storage: TaskStorage, task_id: str) -> list[Path]:
    if not storage.output_root.exists():
        return []
    thumbnail_root = storage.output_root / "thumbnails"
    output_paths: list[Path] = []
    for path in storage.output_root.rglob(f"{task_id}-image-*"):
        try:
            path.relative_to(thumbnail_root)
        except ValueError:
            pass
        else:
            continue
        if _output_index_from_path(path) is None:
            continue
        output_paths.append(path)
    return sorted(
        output_paths,
        key=lambda path: (_output_index_from_path(path) or 999999, storage.output_file(path)),
    )


def _output_index_from_path(path: Path) -> int | None:
    match = re.search(r"-image-(\d+)\.[^.]+$", path.name)
    if not match:
        return None
    return int(match.group(1))
