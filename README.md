# karton memory watcher

This is a tool for [karton](https://github.com/CERT-Polska/karton) workers.

Working for several months in a row, Python processes consumes more and more RAM.
And sometimes calls for GC are not a solution.
This is especially felt when working with libraries that help to parse certain file formats -
at the start, the process takes up 60 megabytes of RAM, and after a couple of months - 400.

This library implements a watcher that monitors the gradual increase in the service's RAM usage and shuts
it upon reaching a set threshold.

### Cases to run karton-memory-watcher is suitable

Every way that can auto-restart your service. For example, I can suggest at least three of them:

1. systemctl service restart policy: `on-failure` / `always`
2. docker service restart policy: `on-failure` / `always` / `unless-stopped`
3. Screen infinite loop: `while true; do your_app; sleep 10; done`

### Installation

You can install it via pip:
```
pip install karton-memory-watcher
```

### How to use it

Simple way:
```python
from karton.core import Consumer
from karton.memory_watcher import implant_watcher, RestartBehavior, RestartRule

class YourConsumer(Consumer):
    pass

if __name__ == "__main__":
    foobar = YourConsumer()
    implant_watcher(
        foobar,
        RestartRule(
            extra_consumed_memory_percent=80,
            # call_before_exit=(close_db_connections, )
            # restart_behavior=RestartBehavior.EXIT_0
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

#### Usage for Producer

It's a bit harder, because karton-memory-watcher relies on hooks that are specific for Karton.core.Consumer and Karton.core.Karton.

To use on Karton.core.Producer, you need to register hooks manually:

```python
from karton.core import Producer
from karton.memory_watcher import implant_watcher, RestartBehavior, RestartRule

class YourProducer(Producer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.watcher = RestartRule(
            extra_consumed_memory_percent=80,
        )
        self.watcher.pre_hook_behavior()
        ...
    
    def your_job(self):
        while True:
            ...
            # after processing your work and saving all states required
            self.watcher.post_hook_behavior()
    

if __name__ == "__main__":
    foobar = YourProducer()
    foobar.your_job()

```

### Alternatives ways for restart policies

#### Systemctl:

In January 2023 there is a nice feature request about MemoryMax policy:
https://github.com/systemd/systemd/issues/25966

Also writing your own agent that will track memory leaks and send systemctl service to restart (but be careful not to kill ongoing tasks!).

#### Docker

AFAIK docker does not have a capability to send SIGINT to container on 'sort' memory limit.

You can implement your own host watcher that will use `docker stats --no-stream --format "{{.MemUsage}}" $CONTAINER_NAME` and `docker kill --signal=SIGINT $CONTAINER_NAME`.
