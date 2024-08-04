# Eavesdrop

Eavesdrop is a single-file, dependency-free library implementing a classic publisher-subscriber pattern. 

## Installation

Since Eavesdrop is a single-file library, you can just copy the raw [eavesdrop.py](eavesdrop.py) file into your project. And be sure to have the correct version even if this repository is ever updated.

Alternatively you can use pip to install Eavesdrop directly from GitHub:

```bash 
pip install git+https://github.com/DominikPenk/eavesdrop.git
```

## Usage

The code is documented and (hopefully) easy to understand, so feel free to explore the [source file](eavesdrop.py) for more details.

The key part of Eavesdrop is publishing and describing events. 
Eavesdrop supports three methods for defining events and their payloads:

### 1.Using a Dataclass Decorated with @event
This method is recommended for ensuring consistent data and structure for the events being raised. 
The event class is decorated with the @event decorator and can be published by passing an instance of the event class.
The `@event` decorator internally converts the decorated class to a dataclass and adds the `evt_type` attribute to the class (which is a unique identifier for this event).

```python
from eavesdrop import *

@event
class MyEvent:
    msg: str

listen(MyEvent, lambda evt: print("🎧", evt.msg))

# Publishing the event
publish(MyEvent(msg="Hello, World!"))
```

Expected output:
```bash
🎧 Hello, World!
```

### 2. Using an Event Name and Keyword Arguments
You can publish an event by specifying an event name as a string and passing keyword arguments. 
The keyword arguments will be bundled into a dictionary and passed to the listeners.
A small gotcha here is that the dictionary will be updated with the `event` key before being passed to the listeners.

```python
from eavesdrop import *

listen("my_event", lambda evt: print("🎧", evt))

# Publishing the event
publish(MyEvent("my_event", msg="Hello, World!"))
```

Expected output:
```bash
🎧 {"event": "my_event", "msg": "Hello, World!"}
```

### 3.  Using a Dictionary
Create an event by passing dictionary to the `publish` method. 
This dictionary must contain a `event` key with the name of the event.
We do not recommend to use this method since it is the most error-prone one. 

```python
from eavesdrop import *

listen("my_event", lambda evt: print("🎧", evt))

# Publishing the event
publish({"event:": "my_event", "msg": "Hello, World!"})
```

Expected output:
```bash
🎧 {"event": "my_event", "msg": "Hello, World!"}
```

### Event Scope

In the above example, we published events to the global scope.
Eavesdrop supports publishing events locally from a specific `Publisher`.
To do you just need to inherit from the `eavesdrop.Publisher` class and use the `publish` and `listen` methods:

```python
from eavesdrop import event, Publisher

@event
class MyEvent:
    msg: str

class MyPublisher(Publisher):
    ...

my_publisher = MyPublisher()

my_publisher.listen(MyEvent, lambda evt: print("🎧", evt.msg))

my_publisher.publish(MyEvent(msg="Hello, World!"))
```

The publisher class supports the same three event types as global event publishing.

### Eavesdropping

If you are interested in reacting to all published events of a certain type you can use `eavesdrop.eavesdrop`:

```python
from eavesdrop import *

@event
class MyEvent:
    msg: str

class MyPublisher(Publisher):
    ...

my_publisher = MyPublisher()

eavesdrop(MyEvent, lambda evt: print("", evt.msg))

my_publisher.publish(MyEvent(msg="Local: Hello, World!"))
publish(MyEvent(msg="Global: Hello, World!"))
```

Expected output:
```bash
🔍 Local: Hello, World!
🔍 Global: Hello, World!
```

### Stop Listening

All `listen` methods return a handle with the method `stop_listening()` that can be used to stop the listener.
If you want a listener that only reacts to the next instance of the event you can create a self-deleting one with the `listen_once` and `eavesdrop_once` functions.