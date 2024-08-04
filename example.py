from eavesdrop import *


@event
class MyEvent:
    msg: str


provider = Publisher()


def callback(evt):
    print("✨ The stars align and reveal a message:", evt)


def eavesdrop_callback(evt, provider):
    print("🔍 Eavesdrop Alert! Spotted event:", evt, "by", provider)


# Define 8 different listeners
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
h5 = eavesdrop_once(MyEvent, eavesdrop_callback)


# Publish an event, we expect 8 responses
print("📢 First Event Wave:")
provider.publish(MyEvent("Hello, World!"))

# The one-time listeners (h3, h5 and onetime_decorated_eavesdrop) have already stopped themselves after handling the event.
# Let's also stop listener h2 to prevent it from responding to future events.
h2.stop_listening()

# This event should cause 4 responses
print("\n📢 Second Event Wave:")
provider.publish(MyEvent("Singular Hello, World!"))

# Since we did not define a listener for global occurrences of MyEvent, only the eavesdroppers (2 in total) will respond.
print("\n🌍 Global Broadcast:")
publish(MyEvent("Global Hello, World!"))

print("\n🛑 Stopping all Listeners")
h4.stop_listening()
decorated_eavesdrop.stop_listening()
decorated_listener.stop_listening()

# No listeners are defined anymore, so this event will be lost to the void.
print("\n📢 Final Event Wave")
publish(MyEvent("Message to the Void..."))
