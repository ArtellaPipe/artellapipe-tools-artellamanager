#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains folder tree widgets for Artella Manager
"""

from __future__ import print_function, division, absolute_import

__author__ = "Tomas Poveda"
__license__ = "MIT"
__maintainer__ = "Tomas Poveda"
__email__ = "tpovedatd@gmail.com"

import os
import webbrowser
from functools import partial

from Qt.QtCore import *
from Qt.QtWidgets import *
from Qt.QtGui import *

import tpDcc as tp
from tpDcc.libs.python import fileio, folder
from tpDcc.libs.qt.widgets import message

import artellapipe
from artellapipe.libs.artella.core import artellalib, artellaclasses
from artellapipe.tools.artellamanager.widgets import workers


class ArtellaManagerFolderView(QTreeView, object):

    folderSelected = Signal(object, object)
    refreshSelectedFolder = Signal(list)
    startFetch = Signal(str)

    def __init__(self, parent=None):
        super(ArtellaManagerFolderView, self).__init__(parent)

        self._project = None
        self._thread_pool = QThreadPool()

        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

        self.startFetch.connect(self._on_start_fetch)

    def set_project(self, project):
        self._project = project
        model = ArtellaManagerFolderModel()
        self.setModel(model)
        model.startFetch.connect(self.startFetch.emit)
        project_path = self._project.get_path() if self._project else ''
        if project_path and not os.path.isdir(project_path):
            os.makedirs(project_path)
        model.setRootPath(project_path)
        new_root = model.index(project_path)
        self.setRootIndex(new_root)

        # BUG: We store selection model in a member variable to hold its reference. Otherwise, in PySide the connection
        # will crash Python
        # https://stackoverflow.com/questions/19211430/pyside-segfault-when-using-qitemselectionmodel-with-qlistview
        # https://www.qtcentre.org/threads/58874-QListView-SelectionModel-selectionChanged-Crash
        self._selection_model = self.selectionModel()
        self._selection_model.selectionChanged.connect(self.folderSelected.emit)
        self.hideColumn(1)
        self.hideColumn(2)
        self.hideColumn(3)

    def cleanup(self):
        self._thread_pool.waitForDone(1000)

    def _create_menu(self, item_path):
        menu = QMenu(self)

        refresh_icon = tp.ResourcesMgr().icon('refresh')
        artella_icon = tp.ResourcesMgr().icon('artella')
        eye_icon = tp.ResourcesMgr().icon('eye')
        copy_icon = tp.ResourcesMgr().icon('copy')
        sync_icon = tp.ResourcesMgr().icon('sync')

        refresh_action = QAction(refresh_icon, 'Refresh', menu)
        artella_action = QAction(artella_icon, 'Open in Artella', menu)
        view_locally_action = QAction(eye_icon, 'View Locally', menu)
        copy_path_action = QAction(copy_icon, 'Copy Folder Path', menu)
        copy_artella_path_action = QAction(copy_icon, 'Copy Artella Folder Path', menu)
        sync_action = QAction(sync_icon, 'Sync Recursive', menu)

        menu.addAction(refresh_action)
        menu.addSeparator()
        menu.addAction(artella_action)
        menu.addAction(view_locally_action)
        menu.addSeparator()
        menu.addAction(copy_path_action)
        menu.addAction(copy_artella_path_action)
        menu.addSeparator()
        menu.addAction(sync_action)

        refresh_action.triggered.connect(partial(self._on_refresh_item, item_path))
        view_locally_action.triggered.connect(partial(self._on_open_item_folder, item_path))
        artella_action.triggered.connect(partial(self._on_open_item_in_artella, item_path))
        copy_path_action.triggered.connect(partial(self._on_copy_path, item_path))
        copy_artella_path_action.triggered.connect(partial(self._on_copy_artella_path, item_path))
        sync_action.triggered.connect(partial(self._on_sync_folder, item_path))

        return menu

    def _get_folder_artella_url(self, item_path):
        if not os.path.exists(item_path):
            return

        if os.path.isfile(item_path):
            item_path = os.path.dirname(item_path)

        relative_path = os.path.relpath(item_path, self._project.get_path())
        artella_url = '{}/{}'.format(self._project.get_artella_url(), relative_path)

        return artella_url

    def _on_start_fetch(self, item_path):
        if not self._project:
            return

        dirs_worker = workers.GetArtellaDirsWorker(item_path, self._project)
        dirs_worker.signals.dirsUpdated.connect(self._on_dirs_added)
        dirs_worker.signals.publishedDirsUpdated.connect(self._on_dirs_added)

        self._thread_pool.start(dirs_worker)

    def _on_dirs_added(self, list_of_folders):
        for folder_path in list_of_folders:
            if folder_path and not os.path.isdir(folder_path):
                folder.create_folder(folder_path)

    def _on_published_dirs_added(self, list_of_folders):
        for folder_path in list_of_folders:
            if folder_path and not os.path.isdir(folder_path):
                folder.create_folder(folder_path)

    def _on_refresh_item(self, item_path):

        status = artellalib.get_status(item_path)
        if isinstance(status, artellaclasses.ArtellaDirectoryMetaData):
            for ref_name, ref_data in status.references.items():
                dir_path = ref_data.path
                if ref_data.deleted or ref_data.maximum_version_deleted or os.path.isdir(
                        dir_path) or os.path.splitext(dir_path)[-1]:
                    continue
                folder.create_folder(dir_path)
        elif isinstance(status, artellaclasses.ArtellaAssetMetaData):
            working_folder = self._project.get_working_folder()
            working_path = os.path.join(status.path, working_folder)
            artella_data = artellalib.get_status(working_path)
            if isinstance(artella_data, artellaclasses.ArtellaDirectoryMetaData):
                folder.create_folder(working_path)

        self.refreshSelectedFolder.emit(self.selectedIndexes())

    def _on_open_item_in_artella(self, item_path):
        if not item_path:
            return

        artella_url = self._get_folder_artella_url(item_path)
        if not artella_url:
            return

        webbrowser.open(artella_url)

    def _on_open_item_folder(self, item_path):
        if not os.path.exists(item_path):
            return

        if os.path.isfile(item_path):
            fileio.open_browser(os.path.dirname(item_path))
        else:
            fileio.open_browser(item_path)

    def _on_copy_path(self, item_path):
        if not item_path:
            return
        clipboard = QApplication.clipboard()
        clipboard.setText(item_path, QClipboard.Clipboard)
        if clipboard.supportsSelection():
            clipboard.setText(item_path, QClipboard.Selection)

    def _on_copy_artella_path(self, item_path):
        if not item_path:
            return

        artella_url = self._get_folder_artella_url(item_path)
        if not artella_url:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(artella_url, QClipboard.Clipboard)
        if clipboard.supportsSelection():
            clipboard.setText(artella_url, QClipboard.Selection)

    def _on_sync_folder(self, item_path):
        if not os.path.exists(item_path):
            return

        artellapipe.FilesMgr().sync_paths(item_path, recursive=True)

        message.PopupMessage.success('Folder recursively synced successfully!', parent=self)

        self._on_refresh_item(item_path)

    def _on_context_menu(self, pos):
        """
        Internal callback function that is called when the user wants to show tree context menu
        """

        menu = None
        index = self.indexAt(pos)
        if index and index.isValid():
            item_path = self.model().filePath(index)
            menu = self._create_menu(item_path)

        if menu:
            menu.exec_(self.mapToGlobal(pos))


class ArtellaManagerFolderModel(QFileSystemModel, object):

    startFetch = Signal(str)

    def __init__(self):
        super(ArtellaManagerFolderModel, self).__init__()

        self.setFilter(QDir.Dirs | QDir.NoDotAndDotDot)
        self.setNameFilterDisables(False)

        self._paths_cache = list()

    def canFetchMore(self, index):
        if index in self._paths_cache:
            return False
        self._paths_cache.append(index)

        return True

    def fetchMore(self, index):

        item_path = self.filePath(index)
        if item_path in self._paths_cache:
            return super(ArtellaManagerFolderModel, self).fetchMore(index)

        self._paths_cache.append(item_path)
        self.startFetch.emit(item_path)

        return super(ArtellaManagerFolderModel, self).fetchMore(index)
