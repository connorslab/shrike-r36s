import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location("port_mdns", Path(__file__).parents[1] / "mdns.py")
mdns = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mdns)


@pytest.mark.parametrize("hosts", ["hosts: files dns\n", "  hosts: files resolve dns\n", ""])
def test_private_resolver_configuration_is_idempotent(tmp_path, hosts):
    (tmp_path / "etc").mkdir()
    nss = tmp_path / "etc/nsswitch.conf"
    nss.write_text("passwd: files\n" + hosts + "group: files\n")
    mdns.configure(tmp_path)
    first = nss.read_text()
    mdns.configure(tmp_path)
    assert nss.read_text() == first
    assert first.count(mdns.HOSTS) == 1
    assert "passwd: files\n" in first and "group: files\n" in first
    config = (tmp_path / "etc/avahi/shrike-mdns.conf").read_text()
    assert "enable-dbus=no" in config
    assert "disable-publishing=yes" in config
    assert "enable-reflector=no" in config
