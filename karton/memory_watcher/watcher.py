import time
from enum import Enum
from typing import Callable

import karton.core
import psutil


class RestartBehavior(Enum):
    # We cannot exit by raising exception - there is an exception handler:
    # https://github.com/CERT-Polska/karton/blob/2d10bd432928354a2030a0ee8aa976b64f4acb63/karton/core/karton.py#L301
    # RAISE_EXCEPTION = -1
    EXIT_0 = 1
    EXIT_1 = 2


class MemoryWatcherExitException(Exception):
    pass


class RestartRule:
    def __init__(
        self,
        call_before_exit: tuple[Callable] = tuple(),
        proceed_tasks: int = None,
        elapsed_time: int = None,
        extra_consumed_memory_percent: int = None,
        extra_consumed_megabytes: int = None,
        restart_behavior: RestartBehavior = RestartBehavior.EXIT_0,
    ):
        """
        Body of restart routine
        At least one of parameters should be set:

        :param call_before_exit: one or more functions that need to call before exit
        :param proceed_tasks: count of tasks to proceed for restart
        :param elapsed_time: how many seconds should pass
        :param extra_consumed_memory_percent: extra memory used in % (100% means twice of memory compared to point before starting first task)
        :param extra_consumed_megabytes: extra memory used in megabytes (e.g. your service at start uses 60MB and you need to kill it if it consumes extra 500+ MB)

        Need to mention that the rule will be
        """
        if all(
            a is None
            for a in (
                proceed_tasks,
                elapsed_time,
                extra_consumed_memory_percent,
                extra_consumed_megabytes,
            )
        ):
            raise Exception("You should set at least one parameter!")

        self.call_before_exit = call_before_exit

        self.rule_proceed_tasks = proceed_tasks
        self.rule_elapsed_time = elapsed_time
        self.rule_extra_consumed_memory_percent = extra_consumed_memory_percent
        self.rule_extra_consumed_megabytes = extra_consumed_megabytes

        self.restart_behavior = restart_behavior

        self.prehooked = False
        self.tasks_counter = None
        self.start_time = None
        self.start_memory_usage = None

    @staticmethod
    def get_process_memory_usage():
        return psutil.Process().memory_info().rss // 1024 // 1024

    def pre_hook_behavior(self, *args, **kwargs):
        """
        Init starting variables
        """
        if not self.prehooked:
            self.tasks_counter = 0
            self.start_memory_usage = self.get_process_memory_usage()
            self.start_time = time.time()
            self.prehooked = True

    def post_hook_behavior(self, *args, **kwargs):
        """
        Check that everything is okay, so we don't need to restart
        """
        self.tasks_counter += 1

        # Trigger on count of proceed tasks (decrease call-based errors)
        if self.rule_proceed_tasks is not None:
            if self.tasks_counter >= self.rule_proceed_tasks:
                self.execute_restart_behavior(
                    f"rule_proceed_tasks: {self.tasks_counter} >= {self.rule_proceed_tasks}"
                )

        # Trigger on elapsed time (decrease time-based errors)
        if self.rule_elapsed_time is not None:
            current_time = time.time()
            if current_time - self.start_time >= self.rule_elapsed_time:
                self.execute_restart_behavior(
                    f"rule_elapsed_time: {current_time} - {self.start_time} >= {self.rule_elapsed_time}"
                )

        # Trigger on memory usage
        if (
            self.rule_extra_consumed_megabytes is not None
            or self.rule_extra_consumed_memory_percent is not None
        ):
            memory_usage = self.get_process_memory_usage()

            if self.rule_extra_consumed_megabytes is not None:
                if (
                    memory_usage - self.start_memory_usage
                    >= self.rule_extra_consumed_megabytes
                ):
                    self.execute_restart_behavior(
                        f"rule_extra_consumed_megabytes: {memory_usage} - {self.start_memory_usage} >= {self.rule_extra_consumed_megabytes}"
                    )

            if self.rule_extra_consumed_memory_percent is not None:
                if (
                    memory_usage / self.start_memory_usage - 1
                    >= self.rule_extra_consumed_memory_percent / 100
                ):
                    self.execute_restart_behavior(
                        f"extra_consumed_memory_percent: {memory_usage} / {self.start_memory_usage} - 1 >= {self.rule_extra_consumed_memory_percent} / 100"
                    )

    def execute_restart_behavior(self, reason):
        print(f"Restart policy triggered, reason: {reason}")

        for call in self.call_before_exit:
            call()

        if self.restart_behavior == RestartBehavior.EXIT_0:
            exit(0)

        if self.restart_behavior == RestartBehavior.EXIT_1:
            exit(1)


def implant_watcher(consumer: karton.core.Consumer, rule: RestartRule):
    consumer.add_pre_hook(rule.pre_hook_behavior, "Karton Memory Watcher pre-hook")
    consumer.add_post_hook(rule.post_hook_behavior, "Karton Memory Watcher post-hook")
    # just in case if someone will call `my_consumer = implant_watcher(my_consumer, ...)`
    return consumer
