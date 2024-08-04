from __future__ import annotations

import tkinter as tk
import warnings
import weakref
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol, Type
from uuid import UUID, uuid4

__all__ = [
    "event",
    "Publisher",
    "ListenerHandle",
    "publish",
    "listen",
    "listen_once",
    "eavesdrop",
    "eavesdrop_once",
    "as_eavesdropper",
]


def event(
    cls=None,
    /,
    **kwargs,
):
    """
    A decorator for turning a class into a dataclass usable as an event.

    Usage:
        @event
        class MyEvent:
            msg: str

        raise_event(MyEvent(msg="Hello, World!"))

    Parameters:
        cls (type, optional): The class to be decorated. If not provided, the decorator returns a wrapper function.
        **kwargs: Additional keyword arguments to be passed to the `dataclass` decorator.

    Returns:
        type or Callable: If `cls` is provided, the decorated class is returned. If `cls` is not provided, a wrapper function is returned.

    """

    def wrap(cls):
        cls.evt_type = uuid4()
        return dataclass(
            cls,
            **kwargs,
        )

    if cls is None:
        return wrap

    return wrap(cls)


ListenerDict = dict[UUID, Callable]


class ListenerCallback(Protocol):
    def __call__(self, evt: Any) -> None: ...

    def stop_listening(self) -> None: ...


class EavesdropperCallback(Protocol):
    def __call__(self, evt: Any, provider: Publisher | None) -> None: ...

    def stop_listening(self) -> None: ...


class ListenerHandle(object):
    def __init__(
        self, provider: Publisher | EventRegistry | None, idx: UUID, evt_type: UUID
    ):
        # Store the provider as a weak reference
        self._provider = weakref.ref(provider) if provider is not None else None
        self._id = idx
        self._evt_type = evt_type

    def stop_listening(self):
        """
        Stop listening to events.

        This method stops the listener from receiving events.

        Parameters:
            None

        Returns:
            None
        """
        if self._provider is None:
            EventRegistry.get_instance().stop_eavsdropping(self)
        else:
            EventRegistry.get_instance().stop_listening(self)


class EventRegistry:
    _instance: EventRegistry | None = None

    def __init__(self):
        if EventRegistry._instance is not None:
            raise RuntimeError(
                "EventRegistry is a singleton, use EventRegistry.get_instance()"
            )

        self._evt_provider_id = uuid4()

        self.events_types: dict[str, UUID] = defaultdict(uuid4)
        self.listeners: dict[UUID, dict[UUID, ListenerDict]] = defaultdict(
            lambda: defaultdict(dict)
        )
        self.eavesdropper: dict[UUID, ListenerDict] = defaultdict(dict)

    def _get_event_id(self, evt: Any) -> UUID:
        if isinstance(evt, dict):
            if "event" not in evt:
                raise RuntimeError("Missing 'event' field in event")
            return self._get_event_id(evt["event"])
        elif isinstance(evt, str):
            return self.get_instance().events[evt]
        elif isinstance(evt, UUID):
            return evt
        try:
            return evt.evt_type
        except AttributeError:
            raise ValueError("'evt' is not a valid event type")

    def _get_publisher_id(self, provider: Publisher | None) -> UUID:
        if provider is None:
            return self._evt_provider_id
        elif not isinstance(provider, Publisher):
            raise ValueError("'provider' must be an EventProvider")
        else:
            if not hasattr(provider, "_evt_provider_id"):
                setattr(provider, "_evt_provider_id", uuid4())
            return provider._evt_provider_id

    @classmethod
    def get_instance(cls) -> EventRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def publish(self, evt: Any, provider: Optional[Publisher] = None, **kwargs) -> None:
        if kwargs and not isinstance(evt, str):
            raise RuntimeError("Cannot pass kwargs if 'evt' is not a string")
        elif kwargs:
            evt = {
                "event": evt,
                **kwargs,
            }

        eid = self._get_event_id(evt)
        pid = self._get_publisher_id(provider)

        listeners = list(self.listeners[pid][eid].values())
        for listener in listeners:
            listener(evt)

        eavesdroppers = list(self.eavesdropper[eid].values())
        for eavesdropper in eavesdroppers:
            eavesdropper(evt, provider)

    def add_listener(
        self,
        evt: Any,
        callback: Callable,
        provider: Optional[Publisher] = None,
        onetime: bool = False,
    ) -> ListenerHandle:
        eid = self._get_event_id(evt)
        lid = uuid4()
        pid = self._get_publisher_id(provider)

        provider = provider or self

        handle = ListenerHandle(provider, lid, eid)

        if onetime:

            def closure(evt):
                callback(evt)
                handle.stop_listening()

            self.listeners[pid][eid][lid] = closure
        else:
            self.listeners[pid][eid][lid] = callback

        return ListenerHandle(provider, lid, eid)

    def stop_listening(self, handle: ListenerHandle) -> None:
        provider: Publisher | EventRegistry | None = handle._provider()
        if provider:
            pid = provider._evt_provider_id
            try:
                self.listeners[pid][handle._evt_type].pop(handle._id)
            except KeyError:
                warnings.warn("Tried to stop listening on a non registered listener")
        else:
            warnings.warn("Provider out of scope")

    def add_eavesdropper(
        self, evt: Any, callback: Callable, onetime: bool = False
    ) -> ListenerHandle:
        eid = self._get_event_id(evt)
        lid = uuid4()

        h = ListenerHandle(None, lid, eid)

        if onetime:

            def closure(evt, provider):
                callback(evt, provider)
                h.stop_listening()

            self.eavesdropper[eid][lid] = closure
        else:
            self.eavesdropper[eid][lid] = callback

        return h

    def stop_eavsdropping(self, handle: ListenerHandle) -> None:
        try:
            self.eavesdropper[handle._evt_type].pop(handle._id)
        except KeyError:
            warnings.warn("Tried to stop eavesdropping on a non registered listener")


class Publisher(object):
    def publish(self, evt: Any, **kwargs):
        """Raises an event from this provider.

        There are three way to raise events:
        1. Raising an class decorated with @event:
            This is the suggested way to raise events since it ensures consistent data arriving at the listeners
            The given class will be passed to the listener callback

        2. By Event name and **kwargs:
            This method will pass the kwargs as a dictionary to the listeners.
            Note: The dictionary will be updated with the `event` key before being passed to the listeners

        3. Raising a dictionary:
            The dictionary must contain an `event` key with the name of the event. We suggest to use method 2 instead
            of this one.

        Args:
            evt (EventClass | str | dict): The event to raise. It can be either a class decorated with `@event`, an event name or dictionary with an `event` key.
            **kwargs: Arguments to pass as a dictionary to listeners. Only valid if evt is a string.
        """
        EventRegistry.get_instance().publish(evt, self, **kwargs)

    def listen(self, event: Any, callback: Callable[[Any], None]) -> ListenerHandle:
        """
        Listen for an event and register a callback function to be called when the event is published.

        Args:
            event (Type[EventClass] | str): The event to listen for. It can be either a class decorated with `@event` or an event name.
            callback (Callable): The function to be called when the event is published. The argument is either an instance of type `event` or a dictionary

        Returns:
            ListenerHandle: A handle to the listener that can be used to stop listening to the event.

        Raises:
            RuntimeError: If the event is not a class decorated with `@event` or an event name.
        """
        return EventRegistry.get_instance().add_listener(event, callback, self, False)

    def listen_once(
        self, event: Type[Any] | UUID, callback: Callable
    ) -> ListenerHandle:
        """
        Listen for an event once and register a callback function to be called when the event is published.
        See `listen` for details how events can be specified.

        Args:
            event (Type[EventClass] | str): The event to listen for. It can be either a class decorated with `@event` or an event name.
            callback (Callable): The function to be called when the event is published. The argument is either an instance of type `event` or a dictionary

        Returns:
            ListenerHandle: A handle to the listener that can be used to stop listening to the event.
        """
        return EventRegistry.get_instance().add_listener(event, callback, self, True)

    def as_listener(
        self, event: Any, ontime: bool = False
    ) -> Callable[[Callable], ListenerCallback]:
        """
        Returns a decorator that turns a callback function into a listener for a given event on the publisher.
        The decorated function will have a `stop_listening` method that can be used to stop listening to the event.

        Args:
            event (Any): The event to listen for. It can be either a class decorated with `@event` or an event name.
            ontime (bool, optional): Whether the eavesdropper should only be active for one event. Defaults to False.
        """

        def wrapper(callback: Callable) -> ListenerCallback:
            h = EventRegistry.get_instance().add_listener(event, callback, self, ontime)
            setattr(callback, "stop_listening", h.stop_listening)
            return callback

        return wrapper

    def connect_tk_event(self, widget: tk.Widget, event: str):
        """
        Forwards a tkinter event to the event system. The widget will be passed to the listener callback

        Args:
            widget (tk.Widget): The Tkinter widget to connect.
            event (str): The event to connect.

        Returns:
            None
        """

        def closure(evt):
            self.publish(event, widget=widget)

        widget.bind(event, closure)


# Global events
def publish(evt: Any, **kwargs):
    """
    Publish a global event with the given `evt` and optional keyword arguments.

    Args:
        evt (Any): The event to be published.
        **kwargs: Optional keyword arguments to be passed to the event.

    Raises:
        RuntimeError: If `kwargs` are provided and `evt` is not a string.

    Returns:
        None
    """
    EventRegistry.get_instance().publish(evt, provider=None, **kwargs)


def listen(evt: Any, callback: Callable) -> ListenerHandle:
    """
    Returns a ListenerHandle after adding a listener for the specified global event using the provided callback.
    See EventProvider.listen for details how events can be specified.

    Parameters:
        event (Type[EventClass] | str): The event to listen for. It can be either a class decorated with `@event` or an event name.
        callback (Callable): The function to be called when the event is published. The argument is either an instance of type `event` or a dictionary

    Returns:
        ListenerHandle: A handle to the listener.
    """
    return EventRegistry.get_instance().add_listener(
        evt, callback, provider=None, onetime=False
    )


def listen_once(evt: Any, callback: Callable) -> ListenerHandle:
    """
    Add a one-time listener for the specified global event using the provided callback.
    See EventProvider.listen for details how events can be specified.

    Args:
        event (Type[EventClass] | str): The event to listen for. It can be either a class decorated with `@event` or an event name.
        callback (Callable): The function to be called when the event is published. The argument is either an instance of type `event` or a dictionary

    Returns:
        ListenerHandle: A handle to the listener that can be used to stop listening to the event.
    """
    return EventRegistry.get_instance().add_listener(
        evt, callback, provider=None, onetime=True
    )


def eavesdrop(evt: Any, callback: Callable) -> ListenerHandle:
    """
    Adds a listener that will be called whenever the event `evt` is published, globally or by any provider.
    See EventProvider.listen for details how events can be specified.

    Args:
        evt (Any): The event to add the eavesdropper for. It can be either a class decorated with `@event` or an event name.
        callback (Callable): The function to be called when the event is published. The first argument is either an instance of type `evt` or a dictionary.
                             The second argument is the provider that published the event or None if it is a global event.
    Returns:
        ListenerHandle: A handle to the eavesdropper that can be used to stop listening to the event.
    """
    return EventRegistry.get_instance().add_eavesdropper(evt, callback, onetime=False)


def eavesdrop_once(evt: Any, callback: Callable) -> ListenerHandle:
    """
    Adds a one-time eavesdropper for the specified event.
    See EventProvider.listen for details how events can be specified.

    Args:
        evt (Any): The event to add the eavesdropper for. It can be either a class decorated with `@event` or an event name.
        callback (Callable): The function to be called when the event is published. The first argument is either an instance of type `evt` or a dictionary.
                             The second argument is the provider that published the event or None if it is a global event.

    Returns:
        ListenerHandle: A handle to the eavesdropper that can be used to stop listening to the event.
    """
    return EventRegistry.get_instance().add_eavesdropper(evt, callback, onetime=True)


def as_eavesdropper(
    evt: Any, ontime: bool = False
) -> Callable[[Callable], EavesdropperCallback]:
    """
    Decorator function that adds an eavesdropper for the specified event to the event registry.
    The decorated function will have a `stop_listening` method that can be used to stop listening to the event.

    Args:
        evt (Any): The event to add the eavesdropper for. It can be either a class decorated with `@event` or an event name.
        ontime (bool, optional): Whether the eavesdropper should only be active for one event. Defaults to False.

    """

    def wrapper(callback: Callable) -> EavesdropperCallback:
        h = EventRegistry.get_instance().add_eavesdropper(evt, callback, ontime)
        setattr(callback, "stop_listening", h.stop_listening)
        return callback

    return wrapper


if __name__ == "__main__":

    @event
    class MyEvent:
        msg: str

    provider = Publisher()

    def callback(evt):
        print("✨ The stars align and reveal a message:", evt)

    def eavesdrop_callback(evt, provider):
        print("🔍 Eavesdrop Alert! Spotted event:", evt, "by", provider)

    @as_eavesdropper(MyEvent)
    def decorated_eavesdrop(evt, provider):
        print("🎨 Decorated Eavesdrop:", evt, "by", provider)

    @as_eavesdropper(MyEvent, ontime=True)
    def onetime_decorated_eavesdrop(evt, provider):
        print("⏰ Ontime Decorated Eavesdrop:", evt, "by", provider)

    @provider.as_listener(MyEvent)
    def decorated_listener(evt):
        print("🎧 Decorated Listener:", evt)

    h1 = provider.listen(MyEvent, callback)
    h2 = provider.listen(MyEvent, callback)
    h3 = provider.listen_once(MyEvent, callback)
    h4 = eavesdrop(MyEvent, eavesdrop_callback)
    eavesdrop_once(MyEvent, eavesdrop_callback)

    print("📢 First Event Wave:")
    provider.publish(MyEvent("Hello, World!"))

    h2.stop_listening()

    print("\n📢 Second Event Wave:")
    provider.publish(MyEvent("Singular Hello, World!"))

    print("\n🌍 Global Broadcast:")
    publish(MyEvent("Global Hello, World!"))

    print("\n🛑 Stopping all Listeners")
    h4.stop_listening()
    decorated_eavesdrop.stop_listening()
    decorated_listener.stop_listening()

    print("\n📢 Final Event Wave")
    publish(MyEvent("Message to the Void..."))
