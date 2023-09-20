import logging
import time
from typing import Callable, Optional, cast

import psutil
import pytest
from karton.core import Task

from karton.memory_watcher import (
    MemoryWatcherExitException,
    RestartBehavior,
    RestartRule,
    implant_watcher,
)


class DummyConsumer:
    """
    Oversimplified karton.core.Consumer class that represents situation with pre-hooks and post-hooks
    """

    def __init__(self):
        self._pre_hooks = []
        self._post_hooks = []

        self.log = logging.Logger("DummyConsumer")

    def process(self, task) -> None:
        return None

    def internal_process(self, task) -> None:
        self.current_task = task

        self._run_pre_hooks()

        self.process(self.current_task)
        saved_exception = None
        self._run_post_hooks(saved_exception)

    def add_pre_hook(
        self, callback: Callable[[Task], None], name: Optional[str] = None
    ) -> None:
        """
        Add a function to be called before processing each task.

        :param callback: Function of the form ``callback(task)`` where ``task``
            is a :class:`karton.Task`
        :param name: Name of the pre-hook
        """
        self._pre_hooks.append((name, callback))

    def add_post_hook(
        self,
        callback: Callable[[Task, Optional[Exception]], None],
        name: Optional[str] = None,
    ) -> None:
        """
        Add a function to be called after processing each task.

        :param callback: Function of the form ``callback(task, exception)``
            where ``task`` is a :class:`karton.Task` and ``exception`` is
            an exception thrown by the :meth:`karton.Consumer.process` function
            or ``None``.
        :param name: Name of the post-hook
        """
        self._post_hooks.append((name, callback))

    def _run_pre_hooks(self) -> None:
        """
        Run registered preprocessing hooks

        :meta private:
        """
        for name, callback in self._pre_hooks:
            try:
                callback(cast(Task, self.current_task))
            except Exception:
                if name:
                    self.log.exception("Pre-hook (%s) failed", name)
                else:
                    self.log.exception("Pre-hook failed")

    def _run_post_hooks(self, exception: Optional[Exception]) -> None:
        """
        Run registered postprocessing hooks

        :param exception: Exception object that was caught while processing the task

        :meta private:
        """
        for name, callback in self._post_hooks:
            try:
                callback(cast(Task, self.current_task), exception)
            except Exception:
                if name:
                    self.log.exception("Post-hook (%s) failed", name)
                else:
                    self.log.exception("Post-hook failed")


def test_init():
    foo_service = DummyConsumer()
    implant_watcher(foo_service, RestartRule(extra_consumed_memory_percent=100))
    foo_service.process(None)


def test_policy_proceed_tasks():
    foo_service = DummyConsumer()
    implant_watcher(
        foo_service,
        RestartRule(proceed_tasks=100, restart_behavior=RestartBehavior.EXIT_0),
    )

    for i in range(99):
        foo_service.internal_process(None)

    with pytest.raises(SystemExit) as exc:
        foo_service.internal_process(None)
        print(exc.value.code)
        assert exc.value.code == 0


def test_policy_elapsed_time():
    foo_service = DummyConsumer()
    implant_watcher(
        foo_service,
        RestartRule(elapsed_time=5, restart_behavior=RestartBehavior.EXIT_0),
    )

    foo_service.internal_process(None)
    time.sleep(2)
    foo_service.internal_process(None)
    time.sleep(4)

    with pytest.raises(SystemExit) as exc:
        foo_service.internal_process(None)
        assert exc.value.code == 0


def test_policy_extra_consumed_memory_percent():
    foo_service = DummyConsumer()
    implant_watcher(
        foo_service,
        RestartRule(
            extra_consumed_memory_percent=15, restart_behavior=RestartBehavior.EXIT_0
        ),
    )

    current_memory_usage = psutil.Process().memory_info().rss // 1024 // 1024
    limit_to_reach = int(current_memory_usage * 0.15) + 1

    print("MB to reach", limit_to_reach)

    foo_service.internal_process(None)
    # 60% of "A"
    runtime_string = "A" * 1024 * 1024 * int(limit_to_reach * 0.7)
    print("Runtime string len", len(runtime_string))
    foo_service.internal_process(None)
    # extra 60% of "A"
    runtime_string += "A" * 1024 * 1024 * int(limit_to_reach * 0.7)

    with pytest.raises(SystemExit) as exc:
        foo_service.internal_process(None)
        assert exc.value.code == 0


def test_policy_extra_consumed_megabytes():
    foo_service = DummyConsumer()
    implant_watcher(
        foo_service,
        RestartRule(
            extra_consumed_megabytes=15, restart_behavior=RestartBehavior.EXIT_0
        ),
    )

    foo_service.internal_process(None)
    # 10 megabytes of "A"
    runtime_string = "A" * 10 * 1024 * 1024
    foo_service.internal_process(None)
    # extra 10 megabytes of "A"
    runtime_string += "A" * 10 * 1024 * 1024

    with pytest.raises(SystemExit) as exc:
        foo_service.internal_process(None)
        assert exc.value.code == 0


def test_exit_via_exception():
    foo_service = DummyConsumer()
    implant_watcher(
        foo_service,
        RestartRule(proceed_tasks=5, restart_behavior=RestartBehavior.EXIT_0),
    )

    for i in range(4):
        foo_service.internal_process(None)

    with pytest.raises(SystemExit) as exc:
        foo_service.internal_process(None)
        assert exc.value.code == 0


def test_exit_via_SystemExit1():
    foo_service = DummyConsumer()
    implant_watcher(
        foo_service,
        RestartRule(proceed_tasks=5, restart_behavior=RestartBehavior.EXIT_1),
    )

    for i in range(4):
        foo_service.internal_process(None)

    with pytest.raises(SystemExit) as exc:
        foo_service.internal_process(None)
        assert exc.value.code == 1
