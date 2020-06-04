#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains files tree widgets for Artella Manager
"""

from __future__ import print_function, division, absolute_import

__author__ = "Tomas Poveda"
__license__ = "MIT"
__maintainer__ = "Tomas Poveda"
__email__ = "tpovedatd@gmail.com"

import os
import getpass
from functools import partial

from Qt.QtCore import *
from Qt.QtWidgets import *
from Qt.QtGui import *

import tpDcc as tp
from tpDcc.libs.python import fileio

from artellapipe.libs.artella.core import artellalib


class ArtellaFileSignals(QObject, object):
    viewLocallyItem = Signal(str)
    openArtellaItem = Signal(str)
    copyFilePath = Signal(str)
    copyArtellaFilePath = Signal(str)
    openFile = Signal(str)
    importFile = Signal(str)
    referenceFile = Signal(str)
    getDepsFile = Signal(str)
    syncFile = Signal(object)
    lockFile = Signal(object)
    unlockFile = Signal(object)
    uploadFile = Signal(object)


class ArtellaFileItem(QTreeWidgetItem, object):
    def __init__(self, path, status=None, metadata=None):
        super(ArtellaFileItem, self).__init__()
        self.SIGNALS = ArtellaFileSignals()
        self._metadata = metadata
        self._is_locked = False
        self._locked_by = ''
        self._is_deleted = False
        self._is_directory = False
        self._locked_by_user = False
        self._local_version = None
        self._server_version = None
        self._path = path
        self._menu = None

        if status:
            self.refresh(status)
        else:
            self.clear()

        self._create_menu()

    @property
    def file_name(self):
        return self.text(0)

    @property
    def path(self):
        return self.data(0, Qt.UserRole)

    @property
    def is_deleted(self):
        return self._is_deleted

    @property
    def is_directory(self):
        return self._is_directory

    @property
    def is_locked(self):
        return self._is_locked

    @is_locked.setter
    def is_locked(self, flag):
        self._is_locked = flag
        self.setText(1, str(self._is_locked))

    @property
    def locked_by_user(self):
        return self._locked_by_user

    @property
    def can_be_updated(self):
        if self._server_version is None:
            return False

        if not os.path.isfile(self.path) or self._local_version != self._server_version:
            return True

        return False

    @property
    def local_version(self):
        return self._local_version

    @property
    def server_version(self):
        return self._server_version

    def refresh(self, status=None):
        if not status and self._path:
            status = artellalib.get_status(self._path)
        if not status:
            self.clear()
            return

        if not hasattr(status, 'references'):
            return
        item_ref = status.references[status.references.keys()[0]]
        self._is_deleted = item_ref.deleted
        self._is_directory = item_ref.is_directory
        if self._is_deleted or self._is_directory:
            return
        self._local_version = item_ref.view_version
        if self._local_version and not os.path.isfile(self._path):
            self._local_version = None
        self._server_version = item_ref.maximum_version
        self._is_locked = item_ref.locked
        self._locked_by_user = False
        if self._is_locked:
            locked_view = item_ref.locked_view
            self._locked_by_user = locked_view == self._metadata.storage_id
        self._locked_by = getpass.getuser() if self._locked_by_user else 'Other User' if self._is_locked else ''
        file_name = os.path.basename(self._path)
        self.setText(0, file_name)
        self.setIcon(0, tp.ResourcesMgr().icon_from_filename(self._path))
        self.setText(1, str(self._is_locked))
        self.setText(2, self._locked_by)
        self.setText(3, str(fileio.get_file_size(self._path)) if self._local_version is not None else '')
        self.setText(4, str(self._local_version) if self._local_version is not None else '')
        self.setText(5, str(self._server_version))
        self.setData(0, Qt.UserRole, self._path)

    def clear(self):
        file_name = os.path.basename(self._path) if self._path else ''
        self.setText(0, file_name)
        self.setIcon(0, tp.ResourcesMgr().icon_from_filename(self._path) if self._path else QIcon())
        self.setText(1, 'False')
        self.setText(2, '')
        self.setText(3, '')
        self.setText(4, '')
        self.setText(5, '')
        self.setData(0, Qt.UserRole, self._path if self._path else '')

    def get_menu(self):
        self._update_menu()
        return self._menu

    def _create_menu(self):
        self._menu = QMenu()

        artella_icon = tp.ResourcesMgr().icon('artella')
        eye_icon = tp.ResourcesMgr().icon('eye')
        lock_icon = tp.ResourcesMgr().icon('lock')
        unlock_icon = tp.ResourcesMgr().icon('unlock')
        upload_icon = tp.ResourcesMgr().icon('upload')
        sync_icon = tp.ResourcesMgr().icon('sync')
        copy_icon = tp.ResourcesMgr().icon('copy')
        open_icon = tp.ResourcesMgr().icon('open')
        import_icon = tp.ResourcesMgr().icon('import')
        reference_icon = tp.ResourcesMgr().icon('reference')
        download_icon = tp.ResourcesMgr().icon('download')

        self._artella_action = QAction(artella_icon, 'Open in Artella', self._menu)
        self._view_locally_action = QAction(eye_icon, 'View Locally', self._menu)
        self._sync_action = QAction(sync_icon, 'Sync', self._menu)
        self._lock_action = QAction(lock_icon, 'Lock', self._menu)
        self._unlock_action = QAction(unlock_icon, 'Unlock', self._menu)
        self._upload_action = QAction(upload_icon, 'Upload New Version', self._menu)
        self._copy_path_action = QAction(copy_icon, 'Copy File Path', self._menu)
        self._copy_artella_path_action = QAction(copy_icon, 'Copy Artella Path', self._menu)
        self._open_action = QAction(open_icon, 'Open File', self._menu)
        self._import_action = QAction(import_icon, 'Import File', self._menu)
        self._reference_action = QAction(reference_icon, 'Reference File', self._menu)
        self._get_dependencies_action = QAction(download_icon, 'Get Dependencies', self._menu)

        self._menu.addAction(self._artella_action)
        self._menu.addAction(self._view_locally_action)
        self._menu.addSeparator()
        self._menu.addAction(self._sync_action)
        self._menu.addSeparator()
        self._menu.addAction(self._lock_action)
        self._menu.addAction(self._unlock_action)
        self._menu.addAction(self._upload_action)
        self._menu.addSeparator()
        self._menu.addAction(self._copy_path_action)
        self._menu.addAction(self._copy_artella_path_action)
        self._menu.addSeparator()
        self._menu.addAction(self._open_action)
        self._menu.addAction(self._import_action)
        self._menu.addAction(self._reference_action)
        self._menu.addAction(self._get_dependencies_action)
        self._menu.addSeparator()

        self._artella_action.triggered.connect(partial(self.SIGNALS.openArtellaItem.emit, self._path))
        self._view_locally_action.triggered.connect(partial(self.SIGNALS.viewLocallyItem.emit, self._path))
        self._copy_path_action.triggered.connect(partial(self.SIGNALS.copyFilePath.emit, self._path))
        self._copy_artella_path_action.triggered.connect(partial(self.SIGNALS.copyArtellaFilePath.emit, self._path))
        self._open_action.triggered.connect(partial(self.SIGNALS.openFile.emit, self._path))
        self._import_action.triggered.connect(partial(self.SIGNALS.importFile.emit, self._path))
        self._reference_action.triggered.connect(partial(self.SIGNALS.referenceFile.emit, self._path))
        self._get_dependencies_action.triggered.connect(partial(self.SIGNALS.getDepsFile.emit, self._path))
        self._sync_action.triggered.connect(partial(self.SIGNALS.syncFile.emit, self))
        self._lock_action.triggered.connect(partial(self.SIGNALS.lockFile.emit, self))
        self._unlock_action.triggered.connect(partial(self.SIGNALS.unlockFile.emit, self))
        self._upload_action.triggered.connect(partial(self.SIGNALS.uploadFile.emit, self))

        self._update_menu()

    def _disable_actions(self):
        self._lock_action.setEnabled(False)
        self._unlock_action.setEnabled(False)
        self._sync_action.setEnabled(False)
        self._upload_action.setEnabled(False)
        self._open_action.setEnabled(False)
        self._import_action.setEnabled(False)
        self._get_dependencies_action.setEnabled(False)

    def _update_menu(self):
        self._disable_actions()

        item_path = self.path
        self._sync_action.setEnabled(self.can_be_updated)
        server_version = self.server_version
        if server_version is None:
            self._upload_action.setEnabled(True)
            self._lock_action.setEnabled(False)
            self._unlock_action.setEnabled(False)
        file_paths_exists = os.path.isfile(item_path) if item_path else False
        item_is_locked = self.is_locked
        locked_by_user = self.locked_by_user

        if not file_paths_exists:
            self._lock_action.setEnabled(False)
            self._unlock_action.setEnabled(False)
            self._upload_action.setEnabled(False)
            self._open_action.setEnabled(False)
        else:
            if os.path.splitext(item_path)[-1] in tp.Dcc.get_extensions():
                self._open_action.setVisible(True)
                self._open_action.setEnabled(True)
                self._import_action.setVisible(True)
                self._import_action.setEnabled(True)
                self._get_dependencies_action.setEnabled(True)
            else:
                self._open_action.setVisible(False)
                self._open_action.setEnabled(False)
                self._import_action.setVisible(False)
                self._import_action.setEnabled(False)
                self._get_dependencies_action.setEnabled(False)

            if not item_is_locked:
                if server_version is not None:
                    self._lock_action.setEnabled(True)
                self._unlock_action.setEnabled(False)
            else:
                self._lock_action.setEnabled(False)
                if locked_by_user:
                    self._unlock_action.setEnabled(True)
                    self._upload_action.setEnabled(True)
                else:
                    self._unlock_action.setEnabled(False)
                    self._upload_action.setEnabled(False)


class ArtellaFilesTree(QTreeWidget, object):
    def __init__(self, project, parent=None):
        self._project = project

        super(ArtellaFilesTree, self).__init__(parent)

        self.setHeaderLabels(['Name', 'Locked', 'Locked By', 'Size (Mb)', 'Local Version', 'Server Version'])
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)
        self.setAlternatingRowColors(True)
        self.setSelectionMode(self.ExtendedSelection)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if not item:
            self.clearSelection()
        super(ArtellaFilesTree, self).mousePressEvent(event)

    def unhide_items(self):
        """
        Unhide all tree items
        """

        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            self.setItemHidden(item, False)

    def filter_names(self, filter_text):
        """
        Hides all tree items with the given text
        :param filter_text: str, text used to filter tree items
        """

        self.unhide_items()

        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            text = str(item.text(0))
            filter_text = str(filter_text)

            # If the filter text is not found on the item text, we hide the item
            if text.find(filter_text) == -1:
                self.setItemHidden(item, True)

    def _on_context_menu(self, pos):
        """
        Internal callback function that is called when the user wants to show tree context menu
        """

        menu = None

        item = self.itemAt(pos)
        if item:
            menu = item.get_menu()

        if menu:
            menu.exec_(self.mapToGlobal(pos))
