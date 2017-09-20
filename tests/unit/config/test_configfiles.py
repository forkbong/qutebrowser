# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:
# Copyright 2017 Florian Bruhin (The Compiler) <mail@qutebrowser.org>

# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for qutebrowser.config.configfiles."""

import os

import pytest

from qutebrowser.config import config, configfiles, configexc
from qutebrowser.utils import utils

from PyQt5.QtCore import QSettings


@pytest.mark.parametrize('old_data, insert, new_data', [
    (None, False, '[general]\n\n[geometry]\n\n'),
    ('[general]\nfooled = true', False, '[general]\n\n[geometry]\n\n'),
    ('[general]\nfoobar = 42', False,
     '[general]\nfoobar = 42\n\n[geometry]\n\n'),
    (None, True, '[general]\nnewval = 23\n\n[geometry]\n\n'),
])
def test_state_config(fake_save_manager, data_tmpdir,
                      old_data, insert, new_data):
    statefile = data_tmpdir / 'state'
    if old_data is not None:
        statefile.write_text(old_data, 'utf-8')

    state = configfiles.StateConfig()

    if insert:
        state['general']['newval'] = '23'
    # WORKAROUND for https://github.com/PyCQA/pylint/issues/574
    if 'foobar' in (old_data or ''):  # pylint: disable=superfluous-parens
        assert state['general']['foobar'] == '42'

    state._save()

    assert statefile.read_text('utf-8') == new_data


@pytest.mark.parametrize('old_config', [
    None,
    'global:\n  colors.hints.fg: magenta',
])
@pytest.mark.parametrize('insert', [True, False])
def test_yaml_config(fake_save_manager, config_tmpdir, old_config, insert):
    autoconfig = config_tmpdir / 'autoconfig.yml'
    if old_config is not None:
        autoconfig.write_text(old_config, 'utf-8')

    yaml = configfiles.YamlConfig()
    yaml.load()

    if insert:
        yaml.values['tabs.show'] = 'never'

    yaml._save()

    text = autoconfig.read_text('utf-8')
    lines = text.splitlines()
    print(lines)

    assert lines[0].startswith('# DO NOT edit this file by hand,')
    assert 'config_version: {}'.format(yaml.VERSION) in lines

    if old_config is None and not insert:
        assert 'global: {}' in lines
    else:
        assert 'global:' in lines

    # WORKAROUND for https://github.com/PyCQA/pylint/issues/574
    if 'magenta' in (old_config or ''):  # pylint: disable=superfluous-parens
        assert '  colors.hints.fg: magenta' in lines
    if insert:
        assert '  tabs.show: never' in lines


@pytest.mark.parametrize('line, text, exception', [
    ('%', 'While parsing', 'while scanning a directive'),
    ('global: 42', 'While loading data', "'global' object is not a dict"),
    ('foo: 42', 'While loading data',
     "Toplevel object does not contain 'global' key"),
    ('42', 'While loading data', "Toplevel object is not a dict"),
])
def test_yaml_config_invalid(fake_save_manager, config_tmpdir,
                             line, text, exception):
    autoconfig = config_tmpdir / 'autoconfig.yml'
    autoconfig.write_text(line, 'utf-8', ensure=True)

    yaml = configfiles.YamlConfig()

    with pytest.raises(configexc.ConfigFileErrors) as excinfo:
        yaml.load()

    assert len(excinfo.value.errors) == 1
    error = excinfo.value.errors[0]
    assert error.text == text
    assert str(error.exception).splitlines()[0] == exception
    assert error.traceback is None


def test_yaml_oserror(fake_save_manager, config_tmpdir):
    autoconfig = config_tmpdir / 'autoconfig.yml'
    autoconfig.ensure()
    autoconfig.chmod(0)
    if os.access(str(autoconfig), os.R_OK):
        # Docker container or similar
        pytest.skip("File was still readable")

    yaml = configfiles.YamlConfig()
    with pytest.raises(configexc.ConfigFileErrors) as excinfo:
        yaml.load()

    assert len(excinfo.value.errors) == 1
    error = excinfo.value.errors[0]
    assert error.text == "While reading"
    assert isinstance(error.exception, OSError)
    assert error.traceback is None


class TestConfigPy:

    """Tests for ConfigAPI and read_config_py()."""

    pytestmark = pytest.mark.usefixtures('config_stub', 'key_config_stub')

    class ConfPy:

        """Helper class to get a confpy fixture."""

        def __init__(self, tmpdir):
            self._confpy = tmpdir / 'config.py'
            self.filename = str(self._confpy)

        def write(self, *lines):
            text = '\n'.join(lines)
            self._confpy.write_text(text, 'utf-8', ensure=True)

        def read(self):
            """Read the config.py via configfiles and check for errors."""
            api = configfiles.read_config_py(self.filename)
            assert not api.errors

    @pytest.fixture
    def confpy(self, tmpdir):
        return self.ConfPy(tmpdir)

    @pytest.mark.parametrize('line', [
        'c.colors.hints.bg = "red"',
        'config.set("colors.hints.bg", "red")',
    ])
    def test_set(self, confpy, line):
        confpy.write(line)
        confpy.read()
        assert config.instance._values['colors.hints.bg'] == 'red'

    @pytest.mark.parametrize('set_first', [True, False])
    @pytest.mark.parametrize('get_line', [
        'c.colors.hints.fg',
        'config.get("colors.hints.fg")',
    ])
    def test_get(self, confpy, set_first, get_line):
        """Test whether getting options works correctly.

        We test this by doing the following:
           - Set colors.hints.fg to some value (inside the config.py with
             set_first, outside of it otherwise).
           - In the config.py, read .fg and set .bg to the same value.
           - Verify that .bg has been set correctly.
        """
        # pylint: disable=bad-config-option
        config.val.colors.hints.fg = 'green'
        if set_first:
            confpy.write('c.colors.hints.fg = "red"',
                         'c.colors.hints.bg = {}'.format(get_line))
            expected = 'red'
        else:
            confpy.write('c.colors.hints.bg = {}'.format(get_line))
            expected = 'green'
        confpy.read()
        assert config.instance._values['colors.hints.bg'] == expected

    @pytest.mark.parametrize('line, mode', [
        ('config.bind(",a", "message-info foo")', 'normal'),
        ('config.bind(",a", "message-info foo", "prompt")', 'prompt'),
    ])
    def test_bind(self, confpy, line, mode):
        confpy.write(line)
        confpy.read()
        expected = {mode: {',a': 'message-info foo'}}
        assert config.instance._values['bindings.commands'] == expected

    @pytest.mark.parametrize('line, key, mode', [
        ('config.unbind("o")', 'o', 'normal'),
        ('config.unbind("y", mode="prompt")', 'y', 'prompt'),
    ])
    def test_unbind(self, confpy, line, key, mode):
        confpy.write(line)
        confpy.read()
        expected = {mode: {key: None}}
        assert config.instance._values['bindings.commands'] == expected

    def test_mutating(self, confpy):
        confpy.write('c.aliases["foo"] = "message-info foo"',
                     'c.aliases["bar"] = "message-info bar"')
        confpy.read()
        assert config.instance._values['aliases']['foo'] == 'message-info foo'
        assert config.instance._values['aliases']['bar'] == 'message-info bar'

    def test_reading_default_location(self, config_tmpdir):
        (config_tmpdir / 'config.py').write_text(
            'c.colors.hints.bg = "red"', 'utf-8')
        configfiles.read_config_py()
        assert config.instance._values['colors.hints.bg'] == 'red'

    def test_reading_missing_default_location(self, config_tmpdir):
        assert not (config_tmpdir / 'config.py').exists()
        configfiles.read_config_py()  # Should not crash

    def test_oserror(self, tmpdir):
        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            configfiles.read_config_py(str(tmpdir / 'foo'))

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert isinstance(error.exception, OSError)
        assert error.text == "Error while reading foo"
        assert error.traceback is None

    def test_nul_bytes(self, confpy):
        confpy.write('\0')
        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            configfiles.read_config_py(confpy.filename)

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert isinstance(error.exception, (TypeError, ValueError))
        assert error.text == "Error while compiling"
        exception_text = 'source code string cannot contain null bytes'
        assert str(error.exception) == exception_text
        assert error.traceback is None

    def test_syntax_error(self, confpy):
        confpy.write('+')
        with pytest.raises(configexc.ConfigFileErrors) as excinfo:
            configfiles.read_config_py(confpy.filename)

        assert len(excinfo.value.errors) == 1
        error = excinfo.value.errors[0]
        assert isinstance(error.exception, SyntaxError)
        assert error.text == "Syntax Error"
        exception_text = 'invalid syntax (config.py, line 1)'
        assert str(error.exception) == exception_text

        tblines = error.traceback.strip().splitlines()
        assert tblines[0] == "Traceback (most recent call last):"
        assert tblines[-1] == "SyntaxError: invalid syntax"
        assert "    +" in tblines
        assert "    ^" in tblines

    def test_unhandled_exception(self, confpy):
        confpy.write("config.load_autoconfig = False", "1/0")
        api = configfiles.read_config_py(confpy.filename)

        assert not api.load_autoconfig

        assert len(api.errors) == 1
        error = api.errors[0]
        assert error.text == "Unhandled exception"
        assert isinstance(error.exception, ZeroDivisionError)

        tblines = error.traceback.strip().splitlines()
        assert tblines[0] == "Traceback (most recent call last):"
        assert tblines[-1] == "ZeroDivisionError: division by zero"
        assert "    1/0" in tblines

    def test_config_val(self, confpy):
        """Using config.val should not work in config.py files."""
        confpy.write("config.val.colors.hints.bg = 'red'")
        api = configfiles.read_config_py(confpy.filename)
        assert len(api.errors) == 1
        error = api.errors[0]
        assert error.text == "Unhandled exception"
        assert isinstance(error.exception, AttributeError)
        message = "'ConfigAPI' object has no attribute 'val'"
        assert str(error.exception) == message

    @pytest.mark.parametrize('line', ["c.foo = 42", "config.set('foo', 42)"])
    def test_config_error(self, confpy, line):
        confpy.write(line, "config.load_autoconfig = False")
        api = configfiles.read_config_py(confpy.filename)

        assert not api.load_autoconfig

        assert len(api.errors) == 1
        error = api.errors[0]
        assert error.text == "While setting 'foo'"
        assert isinstance(error.exception, configexc.NoOptionError)
        assert str(error.exception) == "No option 'foo'"
        assert error.traceback is None

    def test_multiple_errors(self, confpy):
        confpy.write("c.foo = 42", "config.set('foo', 42)", "1/0")
        api = configfiles.read_config_py(confpy.filename)
        assert len(api.errors) == 3

        for error in api.errors[:2]:
            assert error.text == "While setting 'foo'"
            assert isinstance(error.exception, configexc.NoOptionError)
            assert str(error.exception) == "No option 'foo'"
            assert error.traceback is None

        error = api.errors[2]
        assert error.text == "Unhandled exception"
        assert isinstance(error.exception, ZeroDivisionError)
        assert error.traceback is not None


@pytest.fixture
def init_patch(qapp, fake_save_manager, config_tmpdir, data_tmpdir,
               config_stub, monkeypatch):
    monkeypatch.setattr(configfiles, 'state', None)
    yield


def test_init(init_patch, config_tmpdir):
    configfiles.init()

    # Make sure qsettings land in a subdir
    if utils.is_linux:
        settings = QSettings()
        settings.setValue("hello", "world")
        settings.sync()
        assert (config_tmpdir / 'qsettings').exists()

    # Lots of other stuff is tested in test_config.py in test_init
