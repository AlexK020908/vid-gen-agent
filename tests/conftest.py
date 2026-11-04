"""Shared by every test, so no test can reach a real YouTube channel or depend on your current channel settings.

The tests copy the real stickfleet.yaml and channel files. Once youtube.mode was live with a channel connected, two
tests that reach the publish stage uploaded their placeholder videos to the real channel. Three locks stop that:
an empty keychain (a real sign-in is never visible), youtube.mode: stub unless a test asks for live itself, and the
channel settings the tests are written against (clips on, all three gates), whatever the real file says today.
render.pictures is generative unless a test asks for puppet: the real file's puppet at 30 fps made every pipeline
test draw its frames, and the suite ran for over an hour.
"""
import keyring
import keyring.backend
import pytest

from core import config, context
from youtube import auth

TEST_CHANNEL = {"clips_per_video": 8, "gates": ["outline", "script", "render"]}


class EmptyKeyring(keyring.backend.KeyringBackend):
    priority = 1

    def __init__(self) -> None:
        super().__init__()
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service, username):
        return self.store.get((service, username))

    def set_password(self, service, username, password):
        self.store[(service, username)] = password

    def delete_password(self, service, username):
        self.store.pop((service, username), None)


@pytest.fixture(autouse=True)
def no_real_youtube(monkeypatch):
    old = keyring.get_keyring()
    keyring.set_keyring(EmptyKeyring())
    auth._cache.clear()

    real_load = config.load

    def load(root=config.ROOT, data_dir=None, overrides=None):
        overrides = dict(overrides or {})
        overrides["youtube"] = {"mode": "stub", **(overrides.get("youtube") or {})}
        overrides["render"] = {"pictures": "generative", **(overrides.get("render") or {})}
        loaded = real_load(root, data_dir, overrides)
        # the fleet the tests are written against: a real channel added to channels/ mustn't change what they do
        loaded.channels = {cid: c for cid, c in loaded.channels.items() if cid == "zombie"}
        return loaded

    monkeypatch.setattr(config, "load", load)
    monkeypatch.setattr(context, "load", load)
    real_channel = config._channel
    monkeypatch.setattr(config, "_channel", lambda root, raw, path=None: real_channel(root, {**raw, **TEST_CHANNEL}, path))
    yield
    keyring.set_keyring(old)
    auth._cache.clear()
