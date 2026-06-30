from __future__ import annotations

from io import BytesIO
import json
import threading
import tempfile
import time
import unittest
from pathlib import Path

from PIL import Image


def _png_bytes(size: tuple[int, int] = (400, 600)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", size, (120, 180, 160)).save(buffer, format="PNG")
    return buffer.getvalue()


class WebUIStorageTests(unittest.TestCase):
    def test_creates_sharded_task_files_and_lists_newest_first(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            first = storage.create_task("generate")
            second = storage.create_task("edit")

            storage.write_metadata(first.task_id, {"task_id": first.task_id, "created_at": "2026-04-24T01:00:00Z"})
            storage.write_metadata(second.task_id, {"task_id": second.task_id, "created_at": "2026-04-24T02:00:00Z"})

            tasks = storage.list_tasks()
            task_dir_exists = (root / "outputs" / first.task_id).exists() or (root / "inputs" / first.task_id).exists()
            first_source_dir = root / "outputs" / "source-data" / "tasks" / f"{first.task_id[:4]}-{first.task_id[4:6]}-{first.task_id[6:8]}"
            flat_metadata_exists = (root / "outputs" / "source-data" / f"{first.task_id}.metadata.json").exists()

        self.assertEqual([task["task_id"] for task in tasks], [second.task_id, first.task_id])
        self.assertEqual(storage.metadata_path(first.task_id).parent, first_source_dir)
        self.assertFalse(flat_metadata_exists)
        self.assertFalse(task_dir_exists)

    def test_list_tasks_uses_task_index_when_available(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")
            storage.write_metadata(task.task_id, {"task_id": task.task_id, "created_at": "2026-05-09T10:00:00+00:00", "prompt": "indexed"})
            storage.metadata_path(task.task_id).write_text("{broken json", encoding="utf-8")

            tasks = storage.list_tasks()

        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["task_id"], task.task_id)
        self.assertEqual(tasks[0]["prompt"], "indexed")

    def test_history_queries_refresh_stale_completed_index_rows(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")
            created_at = "2026-06-10T14:28:14+00:00"
            storage.write_metadata(
                task.task_id,
                {
                    "task_id": task.task_id,
                    "created_at": created_at,
                    "updated_at": created_at,
                    "status": "completed",
                    "prompt": "stale card",
                    "params": {"size": "1536x1024"},
                    "generated_count": 0,
                    "total_count": 0,
                },
            )
            output_path = storage.write_output(task.task_id, _png_bytes((1536, 1024)), "png", index=1)
            final_metadata = {
                "task_id": task.task_id,
                "created_at": created_at,
                "updated_at": "2026-06-10T14:29:25+00:00",
                "status": "completed",
                "prompt": "stale card",
                "params": {"size": "1536x1024"},
                "generated_count": 1,
                "failed_count": 0,
                "total_count": 1,
                "output_file": storage.output_file(output_path),
                "output_files": [storage.output_file(output_path)],
                "output_url": f"/outputs/{storage.output_file(output_path)}",
                "output_urls": [f"/outputs/{storage.output_file(output_path)}"],
                "outputs": [
                    {
                        "index": 1,
                        "status": "completed",
                        "file": storage.output_file(output_path),
                        "url": f"/outputs/{storage.output_file(output_path)}",
                        "size": "1536x1024",
                    }
                ],
            }
            storage.metadata_path(task.task_id).write_text(json.dumps(final_metadata), encoding="utf-8")

            page = storage.query_task_history(limit=10)
            summary = storage.task_history_summary()

        self.assertEqual(page["tasks"][0]["task_id"], task.task_id)
        self.assertEqual(page["tasks"][0]["generated_count"], 1)
        self.assertEqual(page["tasks"][0]["total_count"], 1)
        self.assertEqual(page["tasks"][0]["thumbnail_url"], f"/api/tasks/{task.task_id}/outputs/1/thumbnail")
        self.assertEqual(page["tasks"][0]["ratio"], "3:2")
        self.assertEqual(page["tasks"][0]["orientation"], "landscape")
        self.assertIn({"value": "3:2", "count": 1}, summary["ratios"])
        self.assertIn({"value": "landscape", "count": 1}, summary["orientations"])

    def test_writes_request_input_and_dated_output_to_separate_roots(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")
            storage.write_request(task.task_id, {"tools": [{"type": "image_generation"}]})
            input_path = storage.write_input(task.task_id, "unsafe name.png", b"input-bytes")
            output_path = storage.write_output(task.task_id, b"png-bytes", "png")

            request = json.loads(storage.request_path(task.task_id).read_text(encoding="utf-8"))
            input_bytes = input_path.read_bytes()
            output_bytes = output_path.read_bytes()

        expected_date = f"{task.task_id[:4]}-{task.task_id[4:6]}-{task.task_id[6:8]}"
        self.assertEqual(request["tools"][0]["type"], "image_generation")
        self.assertEqual(storage.request_path(task.task_id).parent, root / "outputs" / "source-data" / "tasks" / expected_date)
        self.assertEqual(input_path.parent, root / "inputs")
        self.assertEqual(input_path.name, f"{task.task_id}-input-01-unsafe-name.png")
        self.assertEqual(output_path.parent, root / "outputs" / expected_date)
        self.assertEqual(output_path.name, f"{task.task_id}-image-1.png")
        self.assertEqual(storage.output_file(output_path), f"{expected_date}/{task.task_id}-image-1.png")
        self.assertEqual(input_bytes, b"input-bytes")
        self.assertEqual(output_bytes, b"png-bytes")

    def test_writes_output_files_under_task_date_directory(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")

            output_path = storage.write_output(task.task_id, b"png-bytes", "png")

        expected_date = f"{task.task_id[:4]}-{task.task_id[4:6]}-{task.task_id[6:8]}"
        self.assertEqual(output_path.parent, root / "outputs" / expected_date)
        self.assertEqual(output_path.name, f"{task.task_id}-image-1.png")

    def test_write_input_truncates_long_restored_filenames(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("edit")
            long_name = ("20260505010206-c1288460-input-01-" * 8) + "source-image.png"

            input_path = storage.write_input(task.task_id, long_name, b"input-bytes")
            input_bytes = input_path.read_bytes()

        self.assertLessEqual(len(input_path.name.encode("utf-8")), 255)
        self.assertTrue(input_path.name.endswith(".png"))
        self.assertEqual(input_bytes, b"input-bytes")

    def test_write_input_creates_reference_thumbnail_cache(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")

            storage.write_input(task.task_id, "reference.png", _png_bytes(), index=1)
            thumbnail_path = storage.input_thumbnail_path(task.task_id, 1)
            thumbnail_exists = thumbnail_path.exists()
            thumbnail_bytes = thumbnail_path.read_bytes()

        self.assertTrue(thumbnail_exists)
        self.assertLess(len(thumbnail_bytes), len(_png_bytes()))

    def test_writes_multiple_output_files_without_overwriting(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")

            first = storage.write_output(task.task_id, b"first", "png", index=1)
            second = storage.write_output(task.task_id, b"second", "png", index=2)

            first_bytes = first.read_bytes()
            second_bytes = second.read_bytes()

        self.assertEqual(first.name, f"{task.task_id}-image-1.png")
        self.assertEqual(second.name, f"{task.task_id}-image-2.png")
        self.assertEqual(first_bytes, b"first")
        self.assertEqual(second_bytes, b"second")

    def test_storage_writes_output_thumbnail_path_under_output_root(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")
            storage.write_output(task.task_id, b"not image bytes", "png", index=2)

            thumbnail_path = storage.output_thumbnail_path(task.task_id, 2)
            expected_date = f"{task.task_id[:4]}-{task.task_id[4:6]}-{task.task_id[6:8]}"

        self.assertEqual(thumbnail_path.parent, root / "outputs" / "thumbnails" / expected_date)
        self.assertEqual(thumbnail_path.name, f"{task.task_id}-image-2-thumb.jpg")
        self.assertEqual(storage.output_file(thumbnail_path), f"thumbnails/{expected_date}/{task.task_id}-image-2-thumb.jpg")

    def test_deletes_task_files_from_flat_input_and_dated_output(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")
            input_path = storage.write_input(task.task_id, "input.png", b"input")
            output_path = storage.write_output(task.task_id, b"png", "png")
            metadata_path = storage.write_metadata(task.task_id, {"task_id": task.task_id, "input_files": [input_path.name], "output_files": [output_path.name]})
            request_path = storage.write_request(task.task_id, {"model": "gpt-5.4"})

            storage.delete_task(task.task_id)

        self.assertFalse(input_path.exists())
        self.assertFalse(output_path.exists())
        self.assertFalse(metadata_path.exists())
        self.assertFalse(request_path.exists())

    def test_reads_and_migrates_legacy_flat_source_data_files(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source_data_root = root / "outputs" / "source-data"
            source_data_root.mkdir(parents=True)
            task_id = "20260508002828-69cdb328"
            legacy_metadata = source_data_root / f"{task_id}.metadata.json"
            legacy_request = source_data_root / f"{task_id}.request.json"
            legacy_debug = source_data_root / f"{task_id}.debug-sse.jsonl"
            legacy_metadata.write_text(
                json.dumps({"task_id": task_id, "created_at": "2026-05-08T00:28:28Z", "prompt": "legacy"}),
                encoding="utf-8",
            )
            legacy_request.write_text(json.dumps({"model": "gpt-image-2"}), encoding="utf-8")
            legacy_debug.write_text("data: legacy\n", encoding="utf-8")
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=source_data_root)

            metadata_before = storage.read_metadata(task_id)
            result = storage.migrate_source_data_files()
            migrated_metadata = storage.metadata_path(task_id)
            migrated_request = storage.request_path(task_id)
            migrated_debug = storage.debug_sse_path(task_id)
            migrated_prompt = json.loads(migrated_metadata.read_text(encoding="utf-8"))["prompt"]
            migrated_model = json.loads(migrated_request.read_text(encoding="utf-8"))["model"]
            migrated_debug_text = migrated_debug.read_text(encoding="utf-8")
            legacy_metadata_exists = legacy_metadata.exists()
            legacy_request_exists = legacy_request.exists()
            legacy_debug_exists = legacy_debug.exists()
            tasks = storage.list_tasks()

        expected_dir = source_data_root / "tasks" / "2026-05-08"
        self.assertEqual(metadata_before["prompt"], "legacy")
        self.assertEqual(result["moved"], 3)
        self.assertEqual(result["metadata_moved"], 1)
        self.assertEqual(migrated_metadata.parent, expected_dir)
        self.assertFalse(legacy_metadata_exists)
        self.assertFalse(legacy_request_exists)
        self.assertFalse(legacy_debug_exists)
        self.assertEqual(migrated_prompt, "legacy")
        self.assertEqual(migrated_model, "gpt-image-2")
        self.assertEqual(migrated_debug_text, "data: legacy\n")
        self.assertEqual([task["task_id"] for task in tasks], [task_id])

    def test_delete_task_removes_output_and_input_thumbnails(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")
            input_path = storage.write_input(task.task_id, "source.png", b"input")
            output_path = storage.write_output(task.task_id, b"image", "png", index=1)
            output_thumb = storage.output_thumbnail_path(task.task_id, 1)
            input_thumb = storage.input_thumbnail_path(task.task_id, 1)
            output_thumb.parent.mkdir(parents=True, exist_ok=True)
            input_thumb.parent.mkdir(parents=True, exist_ok=True)
            output_thumb.write_bytes(b"thumb")
            input_thumb.write_bytes(b"thumb")
            metadata_path = storage.write_metadata(
                task.task_id,
                {
                    "task_id": task.task_id,
                    "input_files": [input_path.name],
                    "output_files": [storage.output_file(output_path)],
                },
            )

            storage.delete_task(task.task_id)

        self.assertFalse(output_path.exists())
        self.assertFalse(input_path.exists())
        self.assertFalse(output_thumb.exists())
        self.assertFalse(input_thumb.exists())
        self.assertFalse(metadata_path.exists())

    def test_delete_task_removes_legacy_flat_output_files(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("generate")
            legacy_output = root / "outputs" / f"{task.task_id}-image-1.png"
            legacy_output.write_bytes(b"legacy")
            metadata_path = storage.write_metadata(task.task_id, {"task_id": task.task_id, "output_files": [legacy_output.name]})

            storage.delete_task(task.task_id)

        self.assertFalse(legacy_output.exists())

    def test_delete_task_removes_task_prefixed_output_artifacts(self) -> None:
        from codex_image.webui.storage import TaskStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = TaskStorage(input_root=root / "inputs", output_root=root / "outputs", source_data_root=root / "outputs" / "source-data")
            task = storage.create_task("animation_edit")
            artifact = root / "outputs" / task.task_id[:4] / f"{task.task_id}-artifact-original-sprite.png"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_bytes(b"artifact")
            metadata_path = storage.write_metadata(task.task_id, {"task_id": task.task_id, "output_files": []})

            storage.delete_task(task.task_id)

        self.assertFalse(artifact.exists())
        self.assertFalse(metadata_path.exists())
        self.assertFalse(metadata_path.exists())

    def test_queue_storage_persists_waiting_order_and_running_channels(self) -> None:
        from codex_image.webui.storage import QueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            storage = QueueStorage(path)

            storage.enqueue("task-a")
            storage.enqueue("task-b")
            storage.set_running("api:slot-1", "task-c", auth_source="api", account_id=None)

            reloaded = QueueStorage(path).read_state()

        self.assertEqual(reloaded["waiting"], ["task-a", "task-b"])
        self.assertEqual(reloaded["running"]["api:slot-1"]["task_id"], "task-c")
        self.assertIsNone(reloaded["running"]["api:slot-1"]["account_id"])

    def test_queue_storage_promotes_reorders_and_removes_waiting_tasks(self) -> None:
        from codex_image.webui.storage import QueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = QueueStorage(Path(tmp) / "queue.json")
            storage.enqueue("task-a")
            storage.enqueue("task-b")
            storage.enqueue("task-c")

            storage.promote("task-c")
            storage.reorder(["task-b", "task-c", "task-a"])
            storage.remove_waiting("task-c")

            state = storage.read_state()

        self.assertEqual(state["waiting"], ["task-b", "task-a"])

    def test_queue_storage_rejects_invalid_reorder_ids(self) -> None:
        from codex_image.webui.storage import QueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = QueueStorage(Path(tmp) / "queue.json")
            storage.enqueue("task-a")
            storage.enqueue("task-b")

            with self.assertRaises(ValueError):
                storage.reorder(["task-b", "task-missing"])

    def test_queue_storage_rejects_duplicate_reorder_ids(self) -> None:
        from codex_image.webui.storage import QueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = QueueStorage(Path(tmp) / "queue.json")
            storage.enqueue("task-a")
            storage.enqueue("task-b")

            with self.assertRaises(ValueError):
                storage.reorder(["task-a", "task-b", "task-b"])

    def test_queue_storage_rejects_duplicate_current_waiting_reorder_ids(self) -> None:
        from codex_image.webui.storage import QueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = QueueStorage(Path(tmp) / "queue.json")
            storage.write_state({"waiting": ["task-a", "task-a", "task-b"], "running": {}})

            with self.assertRaises(ValueError):
                storage.reorder(["task-a", "task-b", "task-a"])

    def test_queue_storage_write_state_does_not_leave_fixed_tmp_file(self) -> None:
        from codex_image.webui.storage import QueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            storage = QueueStorage(path)

            storage.write_state({"waiting": ["task-a"], "running": {}})

            state = storage.read_state()
            fixed_tmp_exists = (Path(tmp) / "queue.json.tmp").exists()

        self.assertEqual(state["waiting"], ["task-a"])
        self.assertFalse(fixed_tmp_exists)

    def test_queue_storage_corrupt_recovery_uses_distinct_backup_names(self) -> None:
        from codex_image.webui.storage import QueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"

            path.write_text("{not-json", encoding="utf-8")
            QueueStorage(path).read_state()
            path.write_text("{still-not-json", encoding="utf-8")
            QueueStorage(path).read_state()

            corrupt_files = sorted(item.name for item in Path(tmp).glob("queue.corrupt.*.json"))

        self.assertEqual(len(corrupt_files), 2)
        self.assertEqual(len(set(corrupt_files)), 2)

    def test_queue_storage_preserves_corrupt_file_and_starts_empty(self) -> None:
        from codex_image.webui.storage import QueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "queue.json"
            path.write_text("{not-json", encoding="utf-8")
            storage = QueueStorage(path)

            state = storage.read_state()
            corrupt_files = list(Path(tmp).glob("queue.corrupt.*.json"))

        self.assertEqual(state["waiting"], [])
        self.assertEqual(state["running"], {})
        self.assertEqual(len(corrupt_files), 1)

    def test_sqlite_queue_storage_matches_queue_state_api(self) -> None:
        from codex_image.webui.storage import SQLiteQueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = SQLiteQueueStorage(Path(tmp) / "webui.db")
            storage.enqueue("task-a")
            storage.enqueue("task-b")
            storage.set_running("codex:local", "task-c", auth_source="codex")

            state = storage.read_state()

        self.assertEqual(state["waiting"], ["task-a", "task-b"])
        self.assertEqual(state["running"]["codex:local"]["task_id"], "task-c")
        self.assertEqual(state["running"]["codex:local"]["auth_source"], "codex")

    def test_sqlite_queue_storage_imports_legacy_json_once(self) -> None:
        from codex_image.webui.storage import SQLiteQueueStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            legacy = root / "webui-queue.json"
            legacy.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "waiting": ["task-a"],
                        "running": {
                            "codex:local": {
                                "task_id": "task-b",
                                "started_at": "2026-05-01T00:00:00+00:00",
                                "auth_source": "codex",
                                "account_id": None,
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            storage = SQLiteQueueStorage(root / "webui.db", legacy_json_path=legacy)
            state = storage.read_state()
            storage.enqueue("task-c")
            reopened = SQLiteQueueStorage(root / "webui.db", legacy_json_path=legacy).read_state()

        self.assertEqual(state["waiting"], ["task-a"])
        self.assertEqual(state["running"]["codex:local"]["task_id"], "task-b")
        self.assertEqual(reopened["waiting"], ["task-a", "task-c"])

    def test_sqlite_queue_storage_serializes_connection_lifecycle(self) -> None:
        from codex_image.webui.storage import SQLiteQueueStorage

        class ConnectionProxy:
            def __init__(self, connection, on_close):
                self._connection = connection
                self._on_close = on_close

            def close(self):
                try:
                    return self._connection.close()
                finally:
                    self._on_close()

            def __getattr__(self, name):
                return getattr(self._connection, name)

            @property
            def row_factory(self):
                return self._connection.row_factory

            @row_factory.setter
            def row_factory(self, value):
                self._connection.row_factory = value

        class InstrumentedSQLiteQueueStorage(SQLiteQueueStorage):
            def __init__(self, *args, **kwargs):
                self.active_connections = 0
                self.max_active_connections = 0
                self.instrument_lock = threading.Lock()
                self.measure_connections = False
                super().__init__(*args, **kwargs)

            def _connect(self):
                connection = super()._connect()
                if not self.measure_connections:
                    return connection
                with self.instrument_lock:
                    self.active_connections += 1
                    self.max_active_connections = max(self.max_active_connections, self.active_connections)
                time.sleep(0.01)
                return ConnectionProxy(connection, self._connection_closed)

            def _connection_closed(self):
                with self.instrument_lock:
                    self.active_connections -= 1

        with tempfile.TemporaryDirectory() as tmp:
            storage = InstrumentedSQLiteQueueStorage(Path(tmp) / "webui.db")
            storage.measure_connections = True
            threads = [
                threading.Thread(target=storage.enqueue, args=(f"task-{index}",))
                for index in range(8)
            ]
            threads.extend(threading.Thread(target=storage.read_state) for _ in range(8))

            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            state = storage.read_state()

        self.assertEqual(storage.max_active_connections, 1)
        self.assertEqual(len(state["waiting"]), 8)

    def test_reference_asset_storage_dedupes_identical_bytes(self) -> None:
        from codex_image.webui.storage import ReferenceAssetStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = ReferenceAssetStorage(Path(tmp))
            first = storage.create_or_touch("first.png", b"same-bytes", "image/png")
            second = storage.create_or_touch("second.png", b"same-bytes", "image/png")
            image_files = [path for path in Path(tmp).glob("*/*") if path.suffix != ".json"]
            metadata = storage.read_item(first["id"])
            image_bytes = image_files[0].read_bytes()

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["used_count"], 2)
        self.assertEqual(metadata["used_count"], 2)
        self.assertEqual(len(image_files), 1)
        self.assertEqual(image_bytes, b"same-bytes")

    def test_reference_asset_storage_lists_recent_by_last_used(self) -> None:
        from codex_image.webui.storage import ReferenceAssetStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = ReferenceAssetStorage(Path(tmp))
            old = storage.create_or_touch("old.png", b"old-bytes", "image/png")
            new = storage.create_or_touch("new.png", b"new-bytes", "image/png")
            touched_old = storage.touch(old["id"])
            recent = storage.list_recent(limit=2)

        self.assertEqual(touched_old["id"], old["id"])
        self.assertEqual([item["id"] for item in recent], [old["id"], new["id"]])

    def test_reference_asset_storage_prunes_oldest_items_above_limit(self) -> None:
        from codex_image.webui.storage import ReferenceAssetStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = ReferenceAssetStorage(Path(tmp), max_items=3)
            first = storage.create_or_touch("first.png", b"first-bytes", "image/png")
            second = storage.create_or_touch("second.png", b"second-bytes", "image/png")
            third = storage.create_or_touch("third.png", b"third-bytes", "image/png")
            fourth = storage.create_or_touch("fourth.png", b"fourth-bytes", "image/png")
            recent = storage.list_recent(limit=10)
            remaining_ids = {item["id"] for item in recent}
            old_metadata = Path(tmp) / first["id"][:2] / f"{first['id']}.json"
            old_image = Path(tmp) / first["id"][:2] / f"{first['id']}.png"
            old_metadata_exists = old_metadata.exists()
            old_image_exists = old_image.exists()

        self.assertEqual(len(recent), 3)
        self.assertNotIn(first["id"], remaining_ids)
        self.assertIn(second["id"], remaining_ids)
        self.assertIn(third["id"], remaining_ids)
        self.assertIn(fourth["id"], remaining_ids)
        self.assertFalse(old_metadata_exists)
        self.assertFalse(old_image_exists)

    def test_reference_asset_storage_rejects_invalid_ids(self) -> None:
        from codex_image.webui.storage import ReferenceAssetStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = ReferenceAssetStorage(Path(tmp))

            with self.assertRaises(ValueError):
                storage.read_item("../bad")

    def test_reference_asset_storage_list_recent_skips_non_object_json(self) -> None:
        from codex_image.webui.storage import ReferenceAssetStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = ReferenceAssetStorage(root)
            item = storage.create_or_touch("good.png", b"good-bytes", "image/png")
            corrupt_dir = root / "aa"
            corrupt_dir.mkdir(parents=True, exist_ok=True)
            (corrupt_dir / "not-an-object.json").write_text("[]", encoding="utf-8")

            recent = storage.list_recent()

        self.assertEqual([entry["id"] for entry in recent], [item["id"]])

    def test_reference_asset_storage_create_or_touch_recovers_non_object_metadata(self) -> None:
        from codex_image.webui.storage import ReferenceAssetStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = ReferenceAssetStorage(root)
            first = storage.create_or_touch("first.png", b"same-bytes", "image/png")
            metadata_path = root / first["id"][:2] / f"{first['id']}.json"
            metadata_path.write_text("[]", encoding="utf-8")

            recovered = storage.create_or_touch("second.png", b"same-bytes", "image/png")
            metadata = storage.read_item(first["id"])
            image_bytes = storage.image_path(first["id"]).read_bytes()

        self.assertEqual(recovered["id"], first["id"])
        self.assertEqual(recovered["used_count"], 1)
        self.assertEqual(metadata["used_count"], 1)
        self.assertEqual(image_bytes, b"same-bytes")

    def test_reference_asset_storage_rejects_parent_stored_filename(self) -> None:
        from codex_image.webui.storage import ReferenceAssetStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = ReferenceAssetStorage(root)
            item = storage.create_or_touch("safe.png", b"safe-bytes", "image/png")
            (root / "outside.png").write_bytes(b"outside")
            metadata_path = root / item["id"][:2] / f"{item['id']}.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["stored_filename"] = "../outside.png"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                storage.image_path(item["id"])
            recent = storage.list_recent()

        self.assertEqual(recent, [])

    def test_reference_asset_storage_rejects_absolute_stored_filename(self) -> None:
        from codex_image.webui.storage import ReferenceAssetStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = ReferenceAssetStorage(root)
            item = storage.create_or_touch("safe.png", b"safe-bytes", "image/png")
            outside_path = root / "absolute.png"
            outside_path.write_bytes(b"outside")
            metadata_path = root / item["id"][:2] / f"{item['id']}.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["stored_filename"] = str(outside_path)
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            with self.assertRaises(FileNotFoundError):
                storage.image_path(item["id"])
            recent = storage.list_recent()

        self.assertEqual(recent, [])

    def test_reference_asset_storage_create_or_touch_recovers_tampered_stored_filename(self) -> None:
        from codex_image.webui.storage import ReferenceAssetStorage

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            storage = ReferenceAssetStorage(root)
            first = storage.create_or_touch("first.png", b"same-bytes", "image/png")
            (root / "outside.png").write_bytes(b"outside")
            metadata_path = root / first["id"][:2] / f"{first['id']}.json"
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            metadata["stored_filename"] = "../outside.png"
            metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

            recovered = storage.create_or_touch("second.png", b"same-bytes", "image/png")
            stored = storage.read_item(first["id"])
            image_bytes = storage.image_path(first["id"]).read_bytes()

        self.assertEqual(recovered["id"], first["id"])
        self.assertEqual(recovered["stored_filename"], f"{first['id']}.png")
        self.assertEqual(recovered["used_count"], 1)
        self.assertEqual(stored["stored_filename"], f"{first['id']}.png")
        self.assertEqual(image_bytes, b"same-bytes")

    def test_gallery_creates_lists_updates_and_deletes_items(self) -> None:
        from codex_image.webui.storage import GalleryStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = GalleryStorage(Path(tmp))
            item = storage.create_item(
                name="小美",
                category="portrait",
                filename="../unsafe name.png",
                data=b"portrait-bytes",
                content_type="image/png",
            )
            updated = storage.update_item(item["id"], name="小美新版", category="character")
            listed = storage.list_items(category="character")
            image_bytes = storage.image_path(item["id"]).read_bytes()

            storage.delete_item(item["id"])
            exists_after_delete = (Path(tmp) / item["id"]).exists()

        self.assertEqual(item["name"], "小美")
        self.assertEqual(item["category"], "portrait")
        self.assertEqual(item["filename"], "unsafe-name.png")
        self.assertEqual(updated["name"], "小美新版")
        self.assertEqual(updated["category"], "character")
        self.assertEqual([entry["id"] for entry in listed], [item["id"]])
        self.assertEqual(image_bytes, b"portrait-bytes")
        self.assertFalse(exists_after_delete)

    def test_gallery_replaces_item_image_and_metadata(self) -> None:
        from codex_image.webui.storage import GalleryStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = GalleryStorage(Path(tmp))
            item = storage.create_item(
                name="小美",
                category="portrait",
                filename="portrait.png",
                data=b"old-bytes",
                content_type="image/png",
            )
            old_path = storage.image_path(item["id"])
            updated = storage.replace_item_image(
                item["id"],
                filename="../new portrait.webp",
                data=b"new-bytes",
                content_type="image/webp",
            )
            image_bytes = storage.image_path(item["id"]).read_bytes()
            old_exists_after_replace = old_path.exists()

        self.assertEqual(updated["id"], item["id"])
        self.assertEqual(updated["name"], "小美")
        self.assertEqual(updated["filename"], "new-portrait.webp")
        self.assertEqual(updated["mime_type"], "image/webp")
        self.assertEqual(image_bytes, b"new-bytes")
        self.assertFalse(old_exists_after_replace)

    def test_gallery_manages_persistent_custom_categories_and_item_prompt_notes(self) -> None:
        from codex_image.webui.storage import GalleryStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = GalleryStorage(Path(tmp))
            style_category = storage.create_category("风格参考", prompt_role="风格参考")
            item = storage.create_item(
                name="冷调样片",
                category=style_category["id"],
                filename="style.png",
                data=b"style-bytes",
                content_type="image/png",
                prompt_note="只参考色调和光影，不参考构图。",
            )
            updated_category = storage.update_category(
                style_category["id"],
                name="常用风格",
                prompt_role="风格方向",
                order=5,
            )
            migrated_category = storage.create_category("迁移目标", prompt_role="角色参考")
            storage.delete_category(style_category["id"], move_to=migrated_category["id"])
            reloaded = GalleryStorage(Path(tmp))
            listed = reloaded.list_items(category=migrated_category["id"])
            categories = reloaded.list_categories()

        self.assertEqual(item["prompt_note"], "只参考色调和光影，不参考构图。")
        self.assertEqual(updated_category["name"], "常用风格")
        self.assertEqual(updated_category["prompt_role"], "风格方向")
        self.assertEqual(updated_category["order"], 5)
        self.assertEqual(listed[0]["id"], item["id"])
        self.assertEqual(listed[0]["category"], migrated_category["id"])
        self.assertNotIn(style_category["id"], {category["id"] for category in categories})
        self.assertIn(migrated_category["id"], {category["id"] for category in categories})

    def test_gallery_reorders_categories_and_items_persistently(self) -> None:
        from codex_image.webui.storage import GalleryStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = GalleryStorage(Path(tmp))
            custom_category = storage.create_category("风格参考", prompt_role="风格参考")
            storage.reorder_categories([custom_category["id"], "product", "portrait", "character"])

            first = storage.create_item("一号模特", "portrait", "first.png", b"first", "image/png")
            second = storage.create_item("二号模特", "portrait", "second.png", b"second", "image/png")
            third = storage.create_item("三号模特", "portrait", "third.png", b"third", "image/png")
            storage.reorder_items("portrait", [second["id"], third["id"], first["id"]])
            moved = storage.update_item(third["id"], category="character")

            reloaded = GalleryStorage(Path(tmp))
            categories = reloaded.list_categories()
            portrait_items = reloaded.list_items(category="portrait")
            character_items = reloaded.list_items(category="character")

        self.assertEqual([category["id"] for category in categories[:4]], [custom_category["id"], "product", "portrait", "character"])
        self.assertEqual([item["id"] for item in portrait_items], [second["id"], first["id"]])
        self.assertEqual([item["id"] for item in character_items], [moved["id"]])
        self.assertEqual(portrait_items[0]["order"], 10)
        self.assertEqual(portrait_items[1]["order"], 20)
        self.assertEqual(character_items[0]["order"], 10)

    def test_gallery_rejects_duplicate_names_and_invalid_categories(self) -> None:
        from codex_image.webui.storage import GalleryStorage

        with tempfile.TemporaryDirectory() as tmp:
            storage = GalleryStorage(Path(tmp))
            storage.create_item("Hero Cup", "product", "cup.png", b"cup", "image/png")

            with self.assertRaises(FileExistsError):
                storage.create_item(" hero cup ", "product", "cup2.png", b"cup2", "image/png")

            with self.assertRaises(ValueError):
                storage.create_item("Bad", "other", "bad.png", b"bad", "image/png")
