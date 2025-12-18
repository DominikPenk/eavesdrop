# Eavesdrop

Eavesdrop is a single-file, dependency-free library implementing a small
publisher–subscriber pattern for Python. It provides a tiny API to define
typed events, publish them globally or from a specific publisher, and
register listeners or eavesdroppers.

## Installation

Since Eavesdrop is a single-file library, you can just copy the raw [eavesdrop.py](eavesdrop.py) file into your project. And be sure to have the correct version even if this repository is ever updated.

Alternatively you can use pip to install Eavesdrop directly from GitHub:

```bash 
pip install git+https://github.com/DominikPenk/eavesdrop.git
```

## Usage

The code is documented and (hopefully) easy to understand, so feel free to explore the [source file](eavesdrop.py) for more details.

The key part of Eavesdrop is publishing and describing events. Events are
defined by subclassing the provided `Event` base class; instances of those
subclasses are passed to `publish`.

### Events

Eavesdrop defines events by subclassing the provided `Event` base class.
When you subclass `Event` the library will convert your subclass into a
dataclass and attach a unique `evt_type` identifier to the class.

Example:

```python
from eavesdrop import Event, listen, publish

class MyEvent(Event):
    msg: str

listen(MyEvent, lambda evt: print("🎧", evt.msg))

# Publish a typed event instance
publish(MyEvent(msg="Hello, World!"))
```

Output:

```
🎧 Hello, World!
```

Notes on event forms

This implementation focuses on typed events via `Event` subclasses. The
primary, recommended approach is to define events as subclasses of
`Event` and pass instances of those classes to `publish`.

### Event scope

You can publish events globally (via the module-level `publish`) or from a
specific `Publisher` instance. Use `publish`/`listen` on a `Publisher` to
scope events to that provider:

```python
from eavesdrop import Event, Publisher

class MyEvent(Event):
    msg: str

class MyPublisher(Publisher):
    pass

pub = MyPublisher()

pub.listen(MyEvent, lambda evt: print("🎧", evt.msg))
pub.publish(MyEvent(msg="Hello, World!"))
```

Listeners registered on a `Publisher` only receive events published by that
publisher. The global `listen` and `publish` functions operate on a global
registry.

### Eavesdropping

If you want to observe every publication of a given event type regardless
of provider, register an eavesdropper with `eavesdrop` or
`eavesdrop_once` (the latter removes itself after the first call):

```python
from eavesdrop import Event, Publisher, eavesdrop, publish

class MyEvent(Event):
    msg: str

def all_events(evt, provider):
    print("🔍", evt.msg, "by", provider)

eavesdrop(MyEvent, all_events)

publish(MyEvent(msg="Global hello"))
```

Eavesdroppers receive two arguments: the event instance and the publishing
provider (or `None` for global publishes).

### Stop listening

All `listen` and `eavesdrop` functions return a `ListenerHandle` with the
method `stop_listening()` to unregister the listener. If you only need a
single invocation, use `listen_once` or `eavesdrop_once` which remove the
listener automatically after the first call.

## Try the bundled example

There is an example runner in `example.py`. To try it locally:

```powershell
python example.py
```