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

from artellapipe.core import tool
from artellapipe.tools.artellamanager.widgets import artellamanagerwidget


class ArtellaManager(tool.ArtellaToolWidget, object):
    def __init__(self, project, config, settings, parent):
        super(ArtellaManager, self).__init__(project=project, config=config, settings=settings, parent=parent)

    def ui(self):
        super(ArtellaManager, self).ui()

        self._artellamanager_widget = artellamanagerwidget.ArtellaManagerWidget(project=self._project)
        self.main_layout.addWidget(self._artellamanager_widget)
