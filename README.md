# karton memory watcher

Working for several months in a row, tasks gradually become more and more significant in terms of RAM consumption.
And sometimes forcing a call to the garbage collector doesn't help.
This is especially felt when working with libraries that help to parse certain file formats -
at the start, the process takes up 60 megabytes of RAM, and after a couple of months - 400.

This library is a watcher that monitors the gradual increase in the service's RAM usage and shuts
it upon reaching a set threshold.

### For what ways to run karton consumer is it suitable?

For every way that uses autorestart. For example, I can suggest at least three of them:

1. systemctl service restart policy: `on-failure` / `always`
2. docker service restart policy: `on-failure` / `always` / `unless-stopped`
3. Screen infinite loop: `while true; do your_app; sleep 10; done`

### Installation

You can install it via pip:
```
python3 -m pip install karton-memory-watcher
```

### How to use it

Simple way:
```python
from karton.core import Consumer
from karton.memory_watcher import implant_watcher, RestartBehavior, RestartRule

...
class YourConsumer(Consumer):
    pass

if __name__ == "__main__":
    foobar = YourConsumer()
    implant_watcher(
        foobar,
        RestartRule(
            extra_consumed_memory_percent=80,
            # call_before_exit=(close_db_connections, )
        )
    )
    foobar.loop()
    
```

RestartRule modes:
1. `proceed_tasks`: count of tasks to proceed for restart
2. `elapsed_time`: how many seconds should pass
3. `extra_consumed_memory_percent`: extra memory used in % (100% means twice of memory compared to point before starting first task). It uses megabytes to calculate percents.
4. `extra_consumed_megabytes`: extra memory used in megabytes (e.g. your service at start uses 60MB and you need to kill it if it consumes extra 500+ MB)

You can see usage cases in [tests](./tests).

### Alternatives?

#### Systemctl:

In January 2023 there is a nice feature request about MemoryMax policy:
https://github.com/systemd/systemd/issues/25966

Also writing your own agent that will track memory leaks and send systemctl service to restart (but be careful not to kill ongoing tasks!).

#### Docker

wip, feel free to suggest how to gently restart container to allow task normally proceed