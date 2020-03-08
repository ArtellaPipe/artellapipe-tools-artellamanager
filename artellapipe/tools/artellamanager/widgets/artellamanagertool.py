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

from sentry_sdk import capture_message

from tpDcc.libs.qt.widgets import lightbox

import artellapipe
from artellapipe.tools.artellamanager.core import consts
from artellapipe.tools.artellamanager.widgets import artellamanagerwidget


class ArtellaManager(artellapipe.ToolWidget, object):
    def __init__(self, project, config, settings, parent, mode=consts.ArtellaSyncerMode.ALL):

        self._mode = mode

        super(ArtellaManager, self).__init__(project=project, config=config, settings=settings, parent=parent)

    def get_main_layout(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignTop)

        return main_layout

    def ui(self):
        super(ArtellaManager, self).ui()

        self._artellamanager_widget = artellamanagerwidget.ArtellaManagerWidget(
            project=self._project, mode=self._mode)
        self.main_layout.addWidget(self._artellamanager_widget)

    def setup_signals(self):
        if self._artellamanager_widget._local_widget:
            self._artellamanager_widget._local_widget.syncOk.connect(self._on_local_sync_completed)
            self._artellamanager_widget._local_widget.syncWarning.connect(self._on_local_sync_warning)
            self._artellamanager_widget._local_widget.syncFailed.connect(self._on_local_sync_failed)
        if self._artellamanager_widget._server_widget:
            self._artellamanager_widget._server_widget.workerFailed.connect(self._on_server_worker_failed)
            self._artellamanager_widget._server_widget.syncOk.connect(self._on_server_sync_completed)
            self._artellamanager_widget._server_widget.syncWarning.connect(self._on_server_sync_warning)
            self._artellamanager_widget._server_widget.syncFailed.connect(self._on_server_sync_failed)
            self._artellamanager_widget._server_widget.createAsset.connect(self._on_create_new_asset)
        if self._artellamanager_widget._url_widget:
            self._artellamanager_widget._url_widget.syncOk.connect(self._on_url_sync_completed)
            self._artellamanager_widget._url_widget.syncWarning.connect(self._on_url_sync_warning)
            self._artellamanager_widget._url_widget.syncFailed.connect(self._on_url_sync_failed)

    def _on_local_sync_completed(self, ok_msg):
        self.show_ok_message(ok_msg)

    def _on_local_sync_warning(self, warning_msg):
        self.show_warning_message(warning_msg)

    def _on_local_sync_failed(self, error_msg):
        self.show_error_message(error_msg)

    def _on_server_worker_failed(self, error_msg, trace):
        self.show_error_message(error_msg)
        artellapipe.logger.error('{} | {}'.format(error_msg, trace))
        capture_message('{} | {}'.format(error_msg, trace))
        self.close()

    def _on_server_sync_completed(self, ok_msg):
        self.show_ok_message(ok_msg)

    def _on_server_sync_warning(self, warning_msg):
        self.show_warning_message(warning_msg)

    def _on_server_sync_failed(self, error_msg):
        self.show_error_message(error_msg)

    def _on_url_sync_completed(self, ok_msg):
        self.show_ok_message(ok_msg)

    def _on_url_sync_warning(self, warning_msg):
        self.show_warning_message(warning_msg)

    def _on_url_sync_failed(self, error_msg):
        self.show_error_message(error_msg)

    def _on_create_new_asset(self, item):
        new_asset_dlg = self.NEW_ASSET_DIALOG(project=self._project, asset_path=item.get_path())
        self._lightbox = lightbox.Lightbox(self)
        self._lightbox.set_widget(new_asset_dlg)
        self._lightbox.show()
        new_asset_dlg.show()
