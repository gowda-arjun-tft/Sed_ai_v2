import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from ML.deep_research.layer2.backend.evidence import EvidenceStore
from ML.deep_research.layer2.backend.run_log import log_failure, operational_logger
from ML.deep_research.layer2.ML.evidence_backend import EvidenceBackend
from ML.deep_research.layer2 import run_all
from tests.layer2_fixtures import new_run


def failure(code):
    error = sqlite3.OperationalError("PRIVATE_FACT SECRET_TOKEN SQL_PARAMETERS")
    error.sqlite_errorcode = code
    error.sqlite_errorname = "SQLITE_PROTOCOL" if code == 15 else "SQLITE_TEST"
    return error


class SQLiteReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.run = Path(self.tmp.name)
        self.store = EvidenceStore(self.run)
        self.store.add_text("sample", "EXACT needle ä\nsecond needle")
        self.backend = EvidenceBackend(self.run, version=self.store.snapshot())

    def test_concurrent_tools_with_overlapping_writes(self):
        def work(i):
            if i % 5 == 0:
                self.store.put("probe", str(i), {"n": i})
            else:
                self.assertTrue(self.backend.ls("/sample").entries)
                self.assertEqual(len(self.backend.glob("**/*.txt", "/sample").matches), 1)
                self.assertEqual(len(self.backend.grep("needle", "/sample").matches), 2)
                self.assertIn("EXACT", str(self.backend.read("/sample/0000/000001.txt")))
        with operational_logger(self.store.run), self.store.connect() as anchor:
            anchor.execute("SELECT count(*) FROM members").fetchone()
            self.assertFalse(anchor.in_transaction)
            with ThreadPoolExecutor(max_workers=5) as pool:
                list(pool.map(work, range(150)))
        self.assertEqual(self.store.count("probe"), 30)

    def test_all_tools_retry_partial_results_without_duplicates(self):
        for method, args, source in (
            ("ls", ("/sample",), "names"),
            ("glob", ("**/*.txt", "/sample"), "names"),
            ("grep", ("needle", "/sample"), "documents"),
            ("read", ("/sample/0000/000001.txt",), "body"),
        ):
            with self.subTest(method=method):
                expected = getattr(self.backend, method)(*args)
                original = getattr(self.backend.store, source)
                calls = []
                def flaky(*a, **kw):
                    calls.append(1)
                    if source == "body":
                        if len(calls) <= 2:
                            raise failure(sqlite3.SQLITE_PROTOCOL)
                        return original(*a, **kw)
                    def rows():
                        iterator = original(*a, **kw)
                        try:
                            yield next(iterator)
                            if len(calls) <= 2:
                                raise failure(sqlite3.SQLITE_PROTOCOL)
                            yield from iterator
                        finally:
                            iterator.close()
                    return rows()
                with operational_logger(self.store.run), patch.object(self.backend.store, source, flaky), patch(
                    "ML.deep_research.layer2.ML.evidence_backend.time.sleep",
                ) as sleep:
                    result = getattr(self.backend, method)(*args)
                    if method == "read":
                        self.assertEqual(result.file_data["content"], expected.file_data["content"])
                    else:
                        self.assertEqual(result, expected)
                self.assertEqual(len(calls), 3)
                self.assertEqual([c.args[0] for c in sleep.call_args_list], [0.25, 0.5])

    def test_only_busy_and_protocol_retry_and_log_without_payloads(self):
        config = {"configurable": {"stage": "observations", "job": "observations/000005", "thread_id": "t1"}}
        for code, attempts in [(sqlite3.SQLITE_BUSY, 3), (sqlite3.SQLITE_BUSY | (2 << 8), 3),
                               (sqlite3.SQLITE_PROTOCOL, 3), (sqlite3.SQLITE_LOCKED, 1),
                               (sqlite3.SQLITE_CORRUPT, 1), (sqlite3.SQLITE_CANTOPEN, 1)]:
            with (operational_logger(self.store.run), patch.object(self.backend.store, "body", side_effect=failure(code)) as read,
                 patch("ML.deep_research.layer2.ML.evidence_backend.time.sleep") as sleep,
                 patch("ML.deep_research.layer2.ML.evidence_backend.get_config", return_value=config)):
                with self.assertRaises(sqlite3.OperationalError):
                    self.backend.read("/sample/0000/000001.txt")
            self.assertEqual(read.call_count, attempts)
            self.assertEqual(sleep.call_count, attempts - 1)
        log = (self.store.run / "run.log").read_text()
        for value in ("observations/000005", "t1", "read_file", "evidence.sqlite3", "frames=", "sqlite_code=15"):
            self.assertIn(value, log)
        for value in ("PRIVATE_FACT", "SECRET_TOKEN", "SQL_PARAMETERS"):
            self.assertNotIn(value, log)
        with operational_logger(self.store.run), patch.object(self.backend.store, "body", side_effect=ValueError("PRIVATE_FACT")) as read:
            with self.assertRaises(ValueError):
                self.backend.read("/sample/0000/000001.txt")
        self.assertEqual(read.call_count, 1)

    def test_fresh_query_only_connections_and_early_iterator_cleanup(self):
        original = sqlite3.connect
        connections = []
        def connect(*args, **kwargs):
            db = original(*args, **kwargs)
            connections.append((db, kwargs["timeout"]))
            return db
        with patch("ML.deep_research.layer2.backend.evidence.sqlite3.connect", connect):
            with self.store.connect(read_only=True) as db:
                self.assertEqual(db.execute("PRAGMA busy_timeout").fetchone()[0], 5000)
                with self.assertRaises(sqlite3.OperationalError):
                    db.execute("DELETE FROM paths")
            self.backend.read("/sample/0000/000001.txt")
            self.backend.grep("needle", "/sample", max_count=1)
        self.assertEqual(len({id(db) for db, _ in connections}), len(connections))
        for db, timeout in connections:
            self.assertEqual(timeout, 5)
            with self.assertRaises(sqlite3.ProgrammingError):
                db.execute("SELECT 1")
        with self.store.connect() as db:
            self.assertEqual(db.execute("PRAGMA busy_timeout").fetchone()[0], 60000)

    def test_history_indexing_and_writes_are_outside_retry(self):
        backend = EvidenceBackend(self.run, history=True, thread="t1")
        backend.store.archive("t1", [{"body": "PRIVATE_FACT"}])
        with (operational_logger(self.store.run), patch.object(backend.store, "index_history", side_effect=failure(15)) as index,
              patch("ML.deep_research.layer2.ML.evidence_backend.time.sleep") as sleep):
            with self.assertRaises(sqlite3.OperationalError):
                backend.ls("/")
        self.assertEqual(index.call_count, 1)
        sleep.assert_not_called()
        expected = backend.ls("/")
        with operational_logger(self.store.run), patch.object(backend.store, "index_history", wraps=backend.store.index_history) as index:
            self.assertEqual(backend.ls("/"), expected)
        self.assertEqual(index.call_count, 1)

    def test_execute_failure_reopens_and_closes_every_attempt(self):
        original = sqlite3.connect
        connections = []
        class FaultyConnection(sqlite3.Connection):
            def execute(self, sql, *args, **kwargs):
                if sql.startswith("SELECT b.body") and len(connections) < 3:
                    raise failure(sqlite3.SQLITE_PROTOCOL)
                return super().execute(sql, *args, **kwargs)
        def connect(*args, **kwargs):
            db = original(*args, **kwargs, factory=FaultyConnection)
            connections.append(db)
            return db
        with (operational_logger(self.store.run),
              patch("ML.deep_research.layer2.backend.evidence.sqlite3.connect", connect),
              patch("ML.deep_research.layer2.ML.evidence_backend.time.sleep")):
            self.assertIn("EXACT", str(self.backend.read("/sample/0000/000001.txt")))
        self.assertEqual(len(connections), 3)
        for db in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                db.execute("SELECT 1")

    def test_runner_holds_idle_evidence_connection_and_closes_on_failure(self):
        run = new_run(self.run)
        original = sqlite3.connect
        connections = []
        def connect(*args, **kwargs):
            db = original(*args, **kwargs)
            if str(args[0]).endswith("evidence.sqlite3"):
                connections.append(db)
            return db
        async def stop(store, saver, logger):
            active = []
            for db in connections:
                try:
                    db.execute("SELECT count(*) FROM paths").fetchone()
                    active.append(db)
                except sqlite3.ProgrammingError:
                    pass
            self.assertEqual(len(active), 1)
            self.assertFalse(active[0].in_transaction)
            raise RuntimeError("PRIVATE_STAGE_PAYLOAD")
        with (patch.dict("os.environ", {"OPENAI_API_KEY": "offline"}),
              patch("ML.deep_research.layer2.backend.evidence.sqlite3.connect", connect),
              patch("ML.deep_research.layer2.backend.runner.understand", stop)):
            with self.assertRaises(RuntimeError):
                run_all(run)
        for db in connections:
            with self.assertRaises(sqlite3.ProgrammingError):
                db.execute("SELECT 1")
        self.assertNotIn("PRIVATE_STAGE_PAYLOAD", (run / "run.log").read_text())

    def test_generic_job_failure_frames_and_logger_handler_cleanup(self):
        for _ in range(2):
            with operational_logger(self.store.run) as logger:
                try:
                    raise RuntimeError("PRIVATE_FACT SECRET_TOKEN")
                except RuntimeError as exc:
                    log_failure(logger, "job_exception", exc, job="observations/1")
            self.assertFalse(logger.handlers)
        log = (self.store.run / "run.log").read_text()
        self.assertEqual(log.count("job_exception"), 2)
        self.assertNotIn("PRIVATE_FACT", log)
        self.assertNotIn("SECRET_TOKEN", log)
        self.assertIn("test_generic_job_failure_frames", log)


if __name__ == "__main__":
    unittest.main()
