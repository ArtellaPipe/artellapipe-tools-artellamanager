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

from Qt.QtCore import *
from Qt.QtWidgets import *

from tpDcc.libs.python import python
from tpDcc.libs.qt.core import base

from artellapipe.tools.artellamanager.core import consts
from artellapipe.tools.artellamanager.widgets import localmanager, newassetdialog, servermanager, urlsync


class ArtellaManagerWidget(base.BaseWidget, object):

    LOCAL_MANAGER = localmanager.ArtellaLocalManagerWidget
    SERVER_MANAGER = servermanager.ArtellaServerManagerwidget
    URL_SYNC = urlsync.ArtellaURLSyncWidget
    NEW_ASSET_DIALOG = newassetdialog.ArtellaNewAssetDialog

    def __init__(self, project, mode=consts.ArtellaSyncerMode.ALL, parent=None):

        self._project = project
        self._mode = python.force_list(mode)
        self._local_widget = None
        self._server_widget = None
        self._url_widget = None

        super(ArtellaManagerWidget, self).__init__(parent=parent)

    def get_main_layout(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignTop)

        return main_layout

    def ui(self):
        super(ArtellaManagerWidget, self).ui()

        self._tab = QTabWidget()
        self.main_layout.addWidget(self._tab)

        if consts.ArtellaSyncerMode.ALL in self._mode:
            self._local_widget = self.LOCAL_MANAGER(project=self._project)
            self._server_widget = self.SERVER_MANAGER(project=self._project)
            self._url_widget = self.URL_SYNC(project=self._project)
            self._tab.addTab(self._local_widget, 'Local')
            self._tab.addTab(self._server_widget, 'Server')
            self._tab.addTab(self._url_widget, 'URL')
        else:
            widgets_to_add = list()
            if consts.ArtellaSyncerMode.LOCAL in self._mode:
                self._local_widget = self.LOCAL_MANAGER(project=self._project)
                widgets_to_add.append(('Local', self._local_widget))
            if consts.ArtellaSyncerMode.SERVER in self._mode:
                self._server_widget = self.SERVER_MANAGER(project=self._project)
                widgets_to_add.append(('Server', self._server_widget))
            if consts.ArtellaSyncerMode.URL in self._mode:
                self._url_widget = self.URL_SYNC(project=self._project)
                widgets_to_add.append(('URL', self._url_widget))

            for widget in widgets_to_add:
                self._tab.addTab(widget[1], widget[0])

    def closeEvent(self, event):
        if self._server_widget:
            if self._server_widget.worker_is_running():
                self._server_widget.stop_artella_worker()
        event.accept()
