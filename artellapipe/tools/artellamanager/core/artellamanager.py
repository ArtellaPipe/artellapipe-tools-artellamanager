#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Tool that allow artists to work with Artella local and server files
"""

from __future__ import print_function, division, absolute_import

__author__ = "Tomas Poveda"
__license__ = "MIT"
__maintainer__ = "Tomas Poveda"
__email__ = "tpovedatd@gmail.com"

import artellapipe

# Defines ID of the tool
TOOL_ID = 'artellapipe-tools-artellamanager'

# We skip the reloading of this module when launching the tool
no_reload = True


class ArtellapipeManagerTool(artellapipe.Tool, object):
    def __init__(self, *args, **kwargs):
        super(ArtellapipeManagerTool, self).__init__(*args, **kwargs)

    @classmethod
    def config_dict(cls, file_name=None):
        base_tool_config = artellapipe.Tool.config_dict(file_name=file_name)
        tool_config = {
            'name': 'Artella Manager',
            'id': 'artellapipe-tools-artellamanager',
            'logo': 'artellamanager_logo',
            'icon': 'artella',
            'tooltip': 'Tool to manage Artella server and local files',
            'tags': ['artella', 'manager', 'files'],
            'sentry_id': 'https://040ed0435de64013afb25a47d04e3cf1@sentry.io/1763161',
            'is_checkable': False,
            'is_checked': False,
            'menu_ui': {'label': 'Artella Manager', 'load_on_startup': False, 'color': '', 'background_color': ''},
            'menu': [
                {'label': 'Artella',
                 'type': 'menu', 'children': [{'id': 'artellapipe-tools-artellamanager', 'type': 'tool'}]}],
            'shelf': [
                {'name': 'Artella',
                 'children': [{'id': 'artellapipe-tools-artellamanager', 'display_label': False, 'type': 'tool'}]}
            ]
        }
        base_tool_config.update(tool_config)

        return base_tool_config


class ArtellapipeManagerToolset(artellapipe.Toolset, object):
    ID = TOOL_ID

    def __init__(self, *args, **kwargs):

        self._mode = kwargs.pop('mode', 'all')

        super(ArtellapipeManagerToolset, self).__init__(*args, **kwargs)

    def contents(self):

        from artellapipe.tools.artellamanager.widgets import artellamanagertool

        artella_manager = artellamanagertool.ArtellaManager(
            project=self._project, config=self._config, settings=self._settings, mode=self._mode, parent=self)
        return [artella_manager]
