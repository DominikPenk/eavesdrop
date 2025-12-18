from __future__ import annotations

import tkinter as tk
import warnings
import weakref
from collections import defaultdict
from dataclasses import dataclass, is_dataclass
from typing import (
    Callable,
    ClassVar,
    Optional,
    Protocol,
    TypeAlias,
    TypeVar,
    cast,
    dataclass_transform,
)
from uuid import UUID, uuid4

__all__ = [
    "Event",
    "Publisher",
    "ListenerHandle",
    "publish",
    "listen",
    "listen_once",
    "eavesdrop",
    "eavesdrop_once",
    "as_eavesdropper",
]


@dataclass_transform()
class Event:
    def __init_subclass__(cls) -> None:
        if not is_dataclass(cls):
            cls = dataclass(cls)


GE = TypeVar("GE", bound="Event", contravariant=True)
E = TypeVar("E", bound="Event")

ProviderID: TypeAlias = UUID
ListenerID: TypeAlias = UUID
EventType: TypeAlias = type[E]


class ListenerCallback(Protocol[GE]):
    def __call__(self, evt: GE) -> None: ...

    def stop_listening(self) -> None: ...


class EavesdropperCallback(Protocol[GE]):
    def __call__(self, evt: GE, provider: Optional[Publisher]) -> None: ...

    def stop_listening(self) -> None: ...


class ListenerHandle(object):
    def __init__(
        self,
        provider: Optional[Publisher | EventRegistry],
        idx: ListenerID,
        evt_type: EventType,
    ):
        # Store the provider as a weak reference
        self._provider = weakref.ref(provider) if provider is not None else None
        self._id = idx
        self._evt_type = evt_type

    def stop_listening(self):
        """Stop listening for the event tied to this handle.

        Calling this will unregister the underlying listener or eavesdropper
        so the callable will no longer be invoked for future events.
        """
        if self._provider is None:
            EventRegistry.get_instance().stop_eavsdropping(self)
        else:
            EventRegistry.get_instance().stop_listening(self)


class EventRegistry:
    _instance: ClassVar[Optional[EventRegistry]] = None

    def __init__(self):
        if EventRegistry._instance is not None:
            raise RuntimeError(
                "EventRegistry is a singleton, use EventRegistry.get_instance()"
            )

        self._evt_provider_id = uuid4()

        self.listeners: dict[
            ProviderID,
            dict[EventType, dict[ListenerID, Callable[[Event], None]]],
        ] = defaultdict(lambda: defaultdict(dict))
        self.eavesdropper: dict[
            EventType, dict[ListenerID, Callable[[Event, Optional[Publisher]], None]]
        ] = defaultdict(dict)

    @classmethod
    def get_instance(cls) -> EventRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def publish(
        self,
        evt: Event,
        provider: Optional[Publisher] = None,
    ) -> None:
        publisher_id = (
            provider._evt_provider_id if provider is not None else self._evt_provider_id
        )
        event_type = type(evt)

        listeners = list(self.listeners[publisher_id][event_type].values())
        for listener in listeners:
            listener(evt)

        eavesdroppers = list(self.eavesdropper[event_type].values())
        for eavesdropper in eavesdroppers:
            eavesdropper(evt, provider)

    def add_listener(
        self,
        evt: type[E],
        callback: Callable[[E], None],
        provider: Optional[Publisher] = None,
        onetime: bool = False,
    ) -> ListenerHandle:
        eid = evt
        lid = uuid4()

        actual_provider = provider or self
        pid = actual_provider._evt_provider_id

        handle = ListenerHandle(actual_provider, lid, eid)

        if onetime:

            def closure(evt) -> None:
                callback(evt)
                handle.stop_listening()

            # Note: we ignore type, so the type checker is happy
            self.listeners[pid][eid][lid] = closure  # type: ignore
        else:
            # Note: we ignore type, so the type checker is happy
            self.listeners[pid][eid][lid] = callback  # type: ignore

        return ListenerHandle(actual_provider, lid, eid)

    def stop_listening(self, handle: ListenerHandle) -> None:
        provider = handle._provider() if handle._provider is not None else None
        if provider:
            pid = provider._evt_provider_id
            try:
                self.listeners[pid][handle._evt_type].pop(handle._id)
            except KeyError:
                warnings.warn("Tried to stop listening on a non registered listener")
        else:
            warnings.warn("Provider out of scope")

    def add_eavesdropper(
        self,
        evt: type[E],
        callback: Callable[[E, Optional[Publisher]], None],
        onetime: bool = False,
    ) -> ListenerHandle:
        eid = evt
        lid = uuid4()

        h = ListenerHandle(None, lid, eid)

        if onetime:

            def closure(evt, provider):
                callback(evt, provider)
                h.stop_listening()

            self.eavesdropper[eid][lid] = closure  # type: ignore[assignment]
        else:
            self.eavesdropper[eid][lid] = callback  # type: ignore[assignment]

        return h

    def stop_eavsdropping(self, handle: ListenerHandle) -> None:
        try:
            self.eavesdropper[handle._evt_type].pop(handle._id)
        except KeyError:
            warnings.warn("Tried to stop eavesdropping on a non registered listener")


class Publisher(object):
    def __init__(self):
        self._evt_provider_id = uuid4()

    def publish(self, evt: Event, **kwargs):
        """Publish an event from this provider.

        The `evt` argument can be:
        - an Event subclass instance (preferred),
        - a string event name together with kwargs to construct the event dict, or
        - a dict containing an "event" key.

        If `evt` is a string, any additional keyword arguments are merged into a
        dict before dispatch. Additional kwargs are rejected for non-string
        `evt` values.
        """
        EventRegistry.get_instance().publish(evt, self, **kwargs)

    def listen(self, event: type[E], callback: Callable[[E], None]) -> ListenerHandle:
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
        self, event: type[E], callback: Callable[[E], None]
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
        self, event: type[E], ontime: bool = False
    ) -> Callable[[Callable[[E], None]], ListenerCallback[E]]:
        """
        Returns a decorator that turns a callback function into a listener for a given event on the publisher.
        The decorated function will have a `stop_listening` method that can be used to stop listening to the event.

        Args:
            event (Any): The event to listen for. It can be either a class decorated with `@event` or an event name.
            ontime (bool, optional): Whether the eavesdropper should only be active for one event. Defaults to False.
        """

        def decorator(fn: Callable[[E], None]) -> ListenerCallback[E]:
            h = EventRegistry.get_instance().add_listener(event, fn, self, ontime)
            setattr(fn, "stop_listening", h.stop_listening)
            return cast(ListenerCallback[E], fn)

        return decorator

    def connect_tk_event(self, widget: tk.Widget, event: str):
        """
        Forwards a tkinter event to the event system. The widget will be passed to the listener callback

        Args:
            widget (tk.Widget): The Tkinter widget to connect.
            event (str): The event to connect.

        Returns:
            None
        """
        raise NotImplementedError("Currently not implemented")
        # def closure(evt):
        #     self.publish(event, widget=widget)

        # widget.bind(event, closure)


# Global events
def publish(evt: Event, **kwargs):
    """Publish a global event (no specific provider).

    See :meth:`EventRegistry.publish` for accepted `evt` forms and behaviour.
    """
    EventRegistry.get_instance().publish(evt, provider=None, **kwargs)


def listen(evt: type[E], callback: Callable[[E], None]) -> ListenerHandle:
    """Register a global listener for event `evt`.

    The callback will be called with a single argument: the event object or
    the event dict, depending on how the event was published.
    """
    return EventRegistry.get_instance().add_listener(
        evt, callback, provider=None, onetime=False
    )


def listen_once(evt: type[E], callback: Callable[[E], None]) -> ListenerHandle:
    """Register a one-time global listener. The listener is removed after
    it is called once."""
    return EventRegistry.get_instance().add_listener(
        evt, callback, provider=None, onetime=True
    )


def eavesdrop(
    evt: type[E], callback: Callable[[E, Optional[Publisher]], None]
) -> ListenerHandle:
    """Register a global eavesdropper that receives every publication of
    `evt` from any provider. The callback receives (event, provider).
    """
    return EventRegistry.get_instance().add_eavesdropper(evt, callback, onetime=False)


def eavesdrop_once(
    evt: type[E], callback: Callable[[E, Optional[Publisher]], None]
) -> ListenerHandle:
    """Register a one-time global eavesdropper. The eavesdropper is removed
    automatically after the first call."""
    return EventRegistry.get_instance().add_eavesdropper(evt, callback, onetime=True)


def as_eavesdropper(
    evt: type[E], ontime: bool = False
) -> Callable[[Callable[[E, Optional[Publisher]], None]], EavesdropperCallback[E]]:
    """Return a decorator that registers the decorated function as an
    eavesdropper for `evt`.

    The decorated function will be given a `stop_listening()` attribute which
    can be called to unregister it.
    """

    def wrapper(
        callback: Callable[[E, Optional[Publisher]], None],
    ) -> EavesdropperCallback[E]:
        h = EventRegistry.get_instance().add_eavesdropper(evt, callback, ontime)
        setattr(callback, "stop_listening", h.stop_listening)
        return cast(EavesdropperCallback[E], callback)

    return wrapper


if __name__ == "__main__":

    class MyEvent(Event):
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
