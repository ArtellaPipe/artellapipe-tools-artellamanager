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

import os
import getpass
import webbrowser
from functools import partial

from Qt.QtCore import *
from Qt.QtWidgets import *
from Qt.QtGui import *

import tpDcc as tp
from tpDcc.libs.python import fileio, path as path_utils
from tpDcc.libs.qt.core import base
from tpDcc.libs.qt.widgets import stack, loading, dividers, buttons, message, lineedit, search, progressbar, toast

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

        self.setAlternatingRowColors(True)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._on_context_menu)

    def set_project(self, project):
        self._project = project
        model = ArtellaManagerFolderModel()
        self.setModel(model)
        model.startFetch.connect(self.startFetch.emit)
        self.selectionModel().selectionChanged.connect(self.folderSelected.emit)
        project_path = self._project.get_path() if self._project else ''
        if project_path and not os.path.isdir(project_path):
            os.makedirs(project_path)
        model.setRootPath(project_path)
        new_root = model.index(project_path)
        self.setRootIndex(new_root)
        self.hideColumn(1)
        self.hideColumn(2)
        self.hideColumn(3)

    def _create_menu(self, item_path):
        menu = QMenu(self)

        refresh_icon = tp.ResourcesMgr().icon('refresh')
        artella_icon = tp.ResourcesMgr().icon('artella')
        eye_icon = tp.ResourcesMgr().icon('eye')
        sync_icon = tp.ResourcesMgr().icon('sync')

        refresh_action = QAction(refresh_icon, 'Refresh', menu)
        artella_action = QAction(artella_icon, 'Open in Artella', menu)
        view_locally_action = QAction(eye_icon, 'View Locally', menu)
        sync_action = QAction(sync_icon, 'Sync Recursive', menu)

        menu.addAction(refresh_action)
        menu.addSeparator()
        menu.addAction(artella_action)
        menu.addAction(view_locally_action)
        menu.addSeparator()
        menu.addAction(sync_action)

        refresh_action.triggered.connect(partial(self.refreshSelectedFolder, item_path))
        view_locally_action.triggered.connect(partial(self._on_open_item_folder, item_path))
        artella_action.triggered.connect(partial(self._on_open_item_in_artella, item_path))
        sync_action.triggered.connect(partial(self._on_sync_folder, item_path))

        return menu

    def _on_refresh_item(self):
        self.refreshSelectedFolder.emit(self.selectedIndexes())

    def _on_open_item_in_artella(self, item_path):
        if not os.path.exists(item_path):
            return

        if os.path.isfile(item_path):
            item_path = os.path.dirname(item_path)

        relative_path = os.path.relpath(item_path, self._project.get_path())
        artella_url = '{}/{}'.format(self._project.get_artella_url(), relative_path)
        webbrowser.open(artella_url)

    def _on_open_item_folder(self, item_path):
        if not os.path.exists(item_path):
            return

        if os.path.isfile(item_path):
            fileio.open_browser(os.path.dirname(item_path))
        else:
            fileio.open_browser(item_path)

    def _on_sync_folder(self, item_path):
        if not os.path.exists(item_path):
            return

        artellapipe.FilesMgr().sync_paths(item_path, recursive=True)

        message.PopupMessage.success('Folder recursively synced successfully!', parent=self)

        self._on_refresh_item()

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


class ArtellaFileSignals(QObject, object):
    viewLocallyItem = Signal(str)
    openArtellaItem = Signal(str)
    openFile = Signal(str)
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
        open_icon = tp.ResourcesMgr().icon('open')

        self._artella_action = QAction(artella_icon, 'Open in Artella', self._menu)
        self._view_locally_action = QAction(eye_icon, 'View Locally', self._menu)
        self._sync_action = QAction(sync_icon, 'Sync', self._menu)
        self._lock_action = QAction(lock_icon, 'Lock', self._menu)
        self._unlock_action = QAction(unlock_icon, 'Unlock', self._menu)
        self._upload_action = QAction(upload_icon, 'Upload New Version', self._menu)
        self._open_action = QAction(open_icon, 'Open File', self._menu)

        self._menu.addAction(self._artella_action)
        self._menu.addAction(self._view_locally_action)
        self._menu.addSeparator()
        self._menu.addAction(self._sync_action)
        self._menu.addSeparator()
        self._menu.addAction(self._lock_action)
        self._menu.addAction(self._unlock_action)
        self._menu.addAction(self._upload_action)
        self._menu.addSeparator()
        self._menu.addAction(self._open_action)
        self._menu.addSeparator()

        self._artella_action.triggered.connect(partial(self.SIGNALS.openArtellaItem.emit, self._path))
        self._view_locally_action.triggered.connect(partial(self.SIGNALS.viewLocallyItem.emit, self._path))
        self._open_action.triggered.connect(partial(self.SIGNALS.openFile.emit, self._path))
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
            else:
                self._open_action.setVisible(False)
                self._open_action.setEnabled(False)

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


class ArtellaManagerWidget(base.BaseWidget, object):

    METADATA = None

    def __init__(self, project, parent=None):

        self._project = project
        self._selected_items = None
        self._enabled_ui = False

        self.METADATA = None

        self._check_artella_thread = None
        self._get_dirs_thread = None
        self._get_folder_status_thread = None
        self._get_files_thread = None

        super(ArtellaManagerWidget, self).__init__(parent=parent)

        self._artella_timer = QTimer(self)
        self._artella_timer.setInterval(6000)
        self._artella_timer.timeout.connect(self._on_update_metadata)

        self.METADATA = artellalib.get_metadata()
        self._on_artella_checked(bool(self.METADATA))

    def get_main_layout(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        main_layout.setAlignment(Qt.AlignTop)

        return main_layout

    def ui(self):
        super(ArtellaManagerWidget, self).ui()

        self._message = message.BaseMessage()
        self._message.hide()
        self.main_layout.addWidget(self._message)

        self._toolbar = QToolBar()
        self.main_layout.addWidget(self._toolbar)

        self._lock_btn = buttons.BaseToolButton().image('lock').text_beside_icon().medium()
        self._lock_btn.setText('Lock')
        self._unlock_btn = buttons.BaseToolButton().image('unlock').text_beside_icon().medium()
        self._unlock_btn.setText('Unlock')
        self._sync_btn = buttons.BaseToolButton().image('sync').text_beside_icon().medium()
        self._sync_btn.setText('Sync')
        self._upload_btn = buttons.BaseToolButton().image('upload').text_beside_icon().medium()
        self._upload_btn.setText('Upload')
        self._reset_toolbar()

        self._toolbar.addWidget(self._sync_btn)
        self._toolbar.addSeparator()
        self._toolbar.addWidget(self._lock_btn)
        self._toolbar.addWidget(self._unlock_btn)
        self._toolbar.addSeparator()
        self._toolbar.addWidget(self._upload_btn)
        self._toolbar.addSeparator()

        path_line_layout = QHBoxLayout()
        path_line_layout.setSpacing(2)
        path_line_layout.setContentsMargins(2, 2, 2, 2)
        self.main_layout.addLayout(path_line_layout)
        self._refresh_btn = buttons.BaseToolButton().image('refresh').icon_only()
        self._path_line = lineedit.BaseLineEdit()
        self._path_line.set_prefix_widget(buttons.BaseToolButton().image('folder').icon_only())
        self._path_line.setReadOnly(True)
        path_line_layout.addWidget(self._refresh_btn)
        path_line_layout.addWidget(self._path_line)

        splitter = QSplitter()
        splitter.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        self.main_layout.addWidget(splitter)

        folders_widget = QWidget()
        folders_layout = QVBoxLayout()
        folders_layout.setContentsMargins(2, 2, 2, 2)
        folders_layout.setSpacing(2)
        folders_widget.setLayout(folders_layout)
        self._folders_search = search.SearchFindWidget()
        self._folders_view = ArtellaManagerFolderView()
        self._folders_view.set_project(self._project)
        folders_layout.addWidget(self._folders_search)
        folders_layout.addWidget(dividers.Divider())
        folders_layout.addWidget(self._folders_view)

        self._stack = stack.SlidingOpacityStackedWidget()

        self._loading_widget = FilesLoadingWidget()

        files_widget = QWidget()
        files_layout = QVBoxLayout()
        files_layout.setContentsMargins(2, 2, 2, 2)
        files_layout.setSpacing(2)
        files_widget.setLayout(files_layout)
        self._files_search = search.SearchFindWidget()
        self._files_list = ArtellaFilesTree(self._project)
        files_layout.addWidget(self._files_search)
        files_layout.addWidget(dividers.Divider())
        files_layout.addWidget(self._files_list)

        self._stack.addWidget(files_widget)
        self._stack.addWidget(self._loading_widget)

        self._lock_btn.setEnabled(False)
        self._unlock_btn.setEnabled(False)
        self._sync_btn.setEnabled(False)
        self._upload_btn.setEnabled(False)
        self._refresh_btn.setEnabled(False)
        self._path_line.setEnabled(False)
        self._files_list.setEnabled(False)
        self._folders_view.setEnabled(False)

        splitter.addWidget(folders_widget)
        splitter.addWidget(self._stack)

    def setup_signals(self):
        self._folders_view.startFetch.connect(self._on_start_fetch)
        self._folders_view.folderSelected.connect(self._on_folder_selected)
        self._folders_search.textChanged.connect(self._on_folder_search_text_changed)
        self._files_search.textChanged.connect(self._on_files_search_text_changed)
        self._loading_widget.cancelLoad.connect(self._on_cancel_load)
        self._refresh_btn.clicked.connect(self._on_refresh_selected_folder)
        self._folders_view.refreshSelectedFolder.connect(self._on_refresh_selected_folder)
        self._files_list.itemSelectionChanged.connect(self._on_item_file_selected)
        self._lock_btn.clicked.connect(self._on_lock_selected_files)
        self._unlock_btn.clicked.connect(self._on_unlock_selected_files)
        self._sync_btn.clicked.connect(self._on_sync_selected_files)
        self._upload_btn.clicked.connect(self._on_upload_selected_files)

    def closeEvent(self, event):
        if self._check_artella_thread:
            self._check_artella_thread.deleteLater()
        if self._get_files_thread:
            self._get_files_thread.deleteLater()
        if self._get_folder_status_thread:
            self._get_folder_status_thread.deleteLater()
        if self._get_dirs_thread:
            self._get_dirs_thread.deleteLater()
        super(ArtellaManagerWidget, self).closeEvent(event)

    def _update_toolbar(self):
        self._reset_toolbar(reset_selection=False)

        if not self._selected_items:
            return

        all_can_be_updated = True
        for item in self._selected_items:
            all_can_be_updated = item.can_be_updated
            if not all_can_be_updated:
                break

        self._sync_btn.setEnabled(all_can_be_updated)

        server_version = None
        for item in self._selected_items:
            server_version = item.server_version
            if server_version is not None:
                break

        none_server_version = True
        for item in self._selected_items:
            none_server_version = item.server_version
            if none_server_version is None:
                break

        if server_version is None:
            self._upload_btn.setEnabled(True)
            self._lock_btn.setEnabled(False)
            self._unlock_btn.setEnabled(False)
        else:
            all_file_paths_exists = True
            for item in self._selected_items:
                item_path = item.path
                all_file_paths_exists = os.path.isfile(item_path)
                if not all_file_paths_exists:
                    break

            item_is_locked = False
            for item in self._selected_items:
                item_is_locked = item.is_locked
                if item_is_locked:
                    break

            locked_by_user = True
            for item in self._selected_items:
                locked_by_user = item.locked_by_user
                if not locked_by_user:
                    break

            if not all_file_paths_exists:
                self._lock_btn.setEnabled(False)
                self._unlock_btn.setEnabled(False)
                self._upload_btn.setEnabled(False)
            else:
                if not item_is_locked:
                    if none_server_version is not None:
                        self._lock_btn.setEnabled(True)
                    self._unlock_btn.setEnabled(False)
                else:
                    self._lock_btn.setEnabled(False)
                    if locked_by_user:
                        self._unlock_btn.setEnabled(True)
                        self._upload_btn.setEnabled(True)
                    else:
                        self._unlock_btn.setEnabled(False)
                        self._upload_btn.setEnabled(False)

    def _reset_toolbar(self, reset_selection=True):
        """
        Internal function that resets toolbar status
        """

        self._lock_btn.setEnabled(False)
        self._unlock_btn.setEnabled(False)
        self._sync_btn.setEnabled(False)
        self._upload_btn.setEnabled(False)

        if reset_selection:
            self._selected_items = None

    def _show_loading(self):
        if self._stack.currentIndex() != 1:
            self._stack.setCurrentIndex(1)
            self._loading_widget.reset()

    def _stop_threads(self):
        if self._get_files_thread and self._get_files_worker and self._get_files_thread.isRunning():
            self._get_files_worker.abort()
        if self._get_dirs_thread and self._get_dirs_worker and self._get_dirs_thread.isRunning():
            self._get_dirs_worker.abort()
        if self._get_folder_status_thread and self._get_status_worker and self._get_folder_status_thread.isRunning():
            self._get_status_worker.abort()

    def _artella_not_available(self):
        self._stop_threads()
        self._message.text = 'Artella server is not available! Check that Artella App is running.'
        self._message.theme_type = message.MessageTypes.WARNING
        self._message.show()
        self._set_enable_ui(False)
        self._stack.setCurrentIndex(0)
        self._artella_timer.start()

    def _artella_available(self):
        self._message.hide()
        self._set_enable_ui(True)
        self._folders_view.set_project(self._project)
        self._artella_timer.stop()

    def _set_enable_ui(self, flag):
        if self._enabled_ui == flag:
            return
        self._enabled_ui = flag
        self._lock_btn.setEnabled(flag)
        self._unlock_btn.setEnabled(flag)
        self._sync_btn.setEnabled(flag)
        self._upload_btn.setEnabled(flag)
        self._refresh_btn.setEnabled(flag)
        self._path_line.setEnabled(flag)
        self._files_list.clear()
        self._files_list.setEnabled(flag)
        self._folders_view.setEnabled(flag)

    def _update_selected_folder_files(self, status):
        self._files_list.clear()
        self._stack.setCurrentIndex(0)

        if self._get_files_thread and self._get_files_thread.isRunning():
            self._get_files_thread.wait()

        if not status:
            self._folders_view.setEnabled(True)
            message.PopupMessage.error(
                text='Impossible to retrieve data from Artella. Maybe Artella is down.',
                duration=5,
                parent=self)
            self.METADATA = artellalib.get_metadata()
            if not self.METADATA:
                self._artella_not_available()
            return

        all_files = list()
        if isinstance(status, artellaclasses.ArtellaDirectoryMetaData):
            for ref_name, ref_data in status.references.items():
                dir_path = ref_data.path
                if os.path.isdir(dir_path) or not os.path.splitext(dir_path)[-1]:
                    continue
                all_files.append(dir_path)
        if not all_files:
            self._folders_view.setEnabled(True)
            return

        if not self._get_files_thread or not self._get_files_thread.isRunning():
            self._get_files_thread = QThread(self)
            self._get_files_worker = workers.GetArtellaFilesWorker()
            self._get_files_worker.set_paths(all_files)
            self._get_files_worker.moveToThread(self._get_files_thread)
            self._get_files_thread.started.connect(self._get_files_worker.process)
            self._get_files_thread.finished.connect(self._on_get_files_thread_finished)
            self._get_files_worker.progressStarted.connect(self._on_start_find_files)
            self._get_files_worker.progressTick.connect(self._on_update_find_files)
            self._get_files_worker.progressAbort.connect(self._on_abort_find_files)
            self._get_files_worker.progressDone.connect(self._on_done_find_files)
            self._get_files_worker.progressDone.connect(self._get_files_thread.quit)
            self._get_files_thread.start()

    def _setup_file_item_signals(self, item):
        item.SIGNALS.viewLocallyItem.connect(self._on_open_item_folder)
        item.SIGNALS.openArtellaItem.connect(self._on_open_item_in_artella)
        item.SIGNALS.openFile.connect(self._on_open_file)
        item.SIGNALS.lockFile.connect(self._on_lock_file)
        item.SIGNALS.unlockFile.connect(self._on_unlock_file)
        item.SIGNALS.syncFile.connect(self._on_sync_file)
        item.SIGNALS.uploadFile.connect(self._on_upload_file)
        # item.syncFile

    def _on_folder_search_text_changed(self, text):
        model = self._folders_view.model()
        if model:
            model.setNameFilters(text)

    def _on_files_search_text_changed(self, text):
        self._files_list.filter_names(text)

    def _on_cancel_load(self):
        self._stop_threads()
        self._files_list.clear()
        self._stack.setCurrentIndex(0)
        self._folders_view.setEnabled(True)

    def _on_refresh_selected_folder(self, selected_indexes=None):
        if self._get_folder_status_thread and self._get_folder_status_thread.isRunning():
            return

        if not selected_indexes:
            selected_indexes = self._folders_view.selectedIndexes()
        if not selected_indexes:
            self._files_list.clear()
            self._path_line.setText('')
        else:
            self._show_loading()
            model = self._folders_view.model()
            if model:
                item_path = model.filePath(selected_indexes[0])
                self._path_line.setText(item_path)
                if not self._get_folder_status_thread or not self._get_folder_status_thread.isRunning():
                    self._get_folder_status_thread = QThread(self)
                    self._get_status_worker = workers.GetArtellaFolderStatusWorker()
                    self._get_status_worker.set_path(item_path)
                    self._get_status_worker.moveToThread(self._get_folder_status_thread)
                    self._get_folder_status_thread.started.connect(self._get_status_worker.process)
                    self._get_folder_status_thread.finished.connect(self._on_get_folder_status_thread_finished)
                    self._get_status_worker.finished.connect(self._get_folder_status_thread.quit)
                    self._get_status_worker.finished.connect(self._on_get_folder_status)
                    self._get_folder_status_thread.start()

    def _on_item_file_selected(self):
        self._reset_toolbar()
        self._selected_items = self._files_list.selectedItems()
        self._update_toolbar()
        if self._selected_items:
            if len(self._selected_items) == 1:
                item_path = self._selected_items[0].path
                self._path_line.setText(item_path)
            else:
                self._path_line.setText('...')

    def _on_start_fetch(self, item_path):
        if not self._get_dirs_thread or not self._get_dirs_thread.isRunning():
            self._get_dirs_thread = QThread(self)
            self._get_dirs_worker = workers.GetArtellaDirsWorker(project=self._project)
            self._get_dirs_worker.set_path(item_path)
            self._get_dirs_worker.moveToThread(self._get_dirs_thread)
            self._get_dirs_thread.started.connect(self._get_dirs_worker.process)
            self._get_dirs_thread.finished.connect(self._on_get_dirs_thread_finished)
            self._get_dirs_worker.dirsUpdated.connect(self._get_dirs_thread.quit)
            self._get_dirs_thread.start()

    def _on_folder_selected(self, selected, *args):
        selected_indexes = selected.indexes()
        self._folders_view.setEnabled(False)
        self._on_refresh_selected_folder(selected_indexes)

    def _on_get_folder_status(self):
        self._get_status_worker.moveToThread(QThread.currentThread())
        status = self._get_status_worker.status
        self._update_selected_folder_files(status)

    def _on_check_finished(self):
        self._check_artella_worker.moveToThread(QThread.currentThread())
        self.METADATA = self._check_artella_worker._metadata
        self._check_artella_worker.deleteLater()

    def _on_check_thread_finished(self):
        if not self._check_artella_thread.isRunning():
            self._check_artella_thread.wait()

    def _on_get_files_thread_finished(self):
        if not self._get_files_thread.isRunning():
            self._get_files_thread.wait()

    def _on_get_folder_status_thread_finished(self):
        if not self._get_folder_status_thread.isRunning():
            self._get_folder_status_thread.wait()

    def _on_get_dirs_thread_finished(self):
        if not self._get_dirs_thread.isRunning():
            self._get_dirs_thread.wait()

    def _on_update_metadata(self):
        if not self._check_artella_thread or not self._check_artella_thread.isRunning():
            self._update_metadata()

    def _update_metadata(self):
        if not self._check_artella_thread or not self._check_artella_thread.isRunning():
            self._check_artella_thread = QThread(self)
            self._check_artella_worker = workers.ArtellaCheckWorker()
            self._check_artella_worker.moveToThread(self._check_artella_thread)
            self._check_artella_thread.started.connect(self._check_artella_worker.process)
            self._check_artella_thread.finished.connect(self._on_check_thread_finished)
            self._check_artella_worker.finished.connect(self._check_artella_thread.quit)
            self._check_artella_worker.finished.connect(self._on_check_finished)
            self._check_artella_worker.artellaAvailable.connect(self._on_artella_checked)
            self._check_artella_thread.start()

    def _on_artella_checked(self, flag):
        if flag:
            self._artella_available()
        else:
            self._artella_not_available()

    def _on_start_find_files(self, total_files):
        self._loading_widget.set_total_files(total_files)
        self._show_loading()

    def _on_done_find_files(self):
        selected_indexes = self._folders_view.selectedIndexes()
        if selected_indexes:
            model = self._folders_view.model()
            if model:
                folder_path = model.filePath(selected_indexes[0])
                folder_files = fileio.get_files(folder_path)
                folder_file_paths = [path_utils.clean_path(os.path.join(folder_path, name)) for name in folder_files]
                folder_files_dict = dict()
                for folder_file_path in folder_file_paths:
                    folder_files_dict[os.path.basename(folder_file_path)] = folder_file_path
                for i in range(self._files_list.topLevelItemCount()):
                    file_item = self._files_list.topLevelItem(i)
                    file_name = file_item.file_name
                    if file_name in folder_files_dict:
                        folder_files_dict.pop(file_name)
                        continue
                if folder_files_dict:
                    for folder_file_name, folder_file_path in folder_files_dict.items():
                        list_item = ArtellaFileItem(path=folder_file_path)
                        if list_item.is_directory or list_item.is_deleted:
                            continue
                        self._setup_file_item_signals(list_item)
                        self._files_list.addTopLevelItem(list_item)

        self._loading_widget.reset()
        self._stack.setCurrentIndex(0)
        self._folders_view.setEnabled(True)

    def _on_abort_find_files(self):
        self._files_list.clear()
        self._stack.setCurrentIndex(0)
        self._loading_widget.reset()

    def _on_update_find_files(self, index, path, status):
        self._loading_widget.set_value(index, path)
        if status:
            list_item = ArtellaFileItem(path=path, status=status, metadata=self.METADATA)
            if list_item.is_directory or list_item.is_deleted:
                return
            self._setup_file_item_signals(list_item)
            self._files_list.addTopLevelItem(list_item)

    def _on_open_item_in_artella(self, item_path):
        if os.path.splitext(item_path)[-1]:
            item_path = os.path.dirname(item_path)

        relative_path = os.path.relpath(item_path, self._project.get_path())
        artella_url = '{}/{}'.format(self._project.get_artella_url(), relative_path)
        webbrowser.open(artella_url)

    def _on_open_item_folder(self, item_path):
        if os.path.splitext(item_path)[-1]:
            fileio.open_browser(os.path.dirname(item_path))
        else:
            fileio.open_browser(item_path)

    def _on_open_file(self, item_path):
        return tp.Dcc.open_file(item_path)

    def _on_lock_file(self, item, refresh_toolbar=True):
        item_path = item.path
        msg = message.PopupMessage.loading('Locking File', parent=self, closable=False)
        error_msg = 'Error while locking file'
        try:
            valid_lock = artellapipe.FilesMgr().lock_file(item_path)
        except Exception as exc:
            error_msg = '{}: {}'.format(error_msg, exc)
            valid_lock = False
        finally:
            msg.close()

        if not valid_lock:
            message.PopupMessage.error(error_msg, parent=self)
        else:
            message.PopupMessage.success('File locked succesfully!', parent=self)
        item.refresh()

        if refresh_toolbar:
            self._update_toolbar()

    def _on_unlock_file(self, item, refresh_toolbar=True):
        item_path = item.path
        msg = message.PopupMessage.loading('Unlocking File', parent=self, closable=False)
        error_msg = 'Error while unlocking file'
        try:
            valid_unlock = artellapipe.FilesMgr().unlock_file(item_path)
        except Exception as exc:
            error_msg = '{}: {}'.format(error_msg, exc)
            valid_unlock = False
        finally:
            msg.close()

        if not valid_unlock:
            message.PopupMessage.error(error_msg, parent=self)
        else:
            message.PopupMessage.success('File unlocked successfully!', parent=self)

        item.refresh()

        if refresh_toolbar:
            self._update_toolbar()

    def _on_sync_file(self, item):
        item_path = item.path
        artellapipe.FilesMgr().sync_files([item_path])

        message.PopupMessage.success('File synced successfully!', parent=self)

        item.refresh()

        self._update_toolbar()

    def _on_upload_file(self, item, refresh_toolbar=True):
        item_path = item.path
        valid_version = artellapipe.FilesMgr().upload_working_version(item_path)

        if valid_version:
            message.PopupMessage.success('File version uploaded successfully!', parent=self)

        item.refresh()

        if refresh_toolbar:
            self._update_toolbar()

    def _on_lock_selected_files(self):
        if not self._selected_items:
            return False

        for item in self._selected_items:
            self._on_lock_file(item, refresh_toolbar=False)

        self._update_toolbar()

    def _on_unlock_selected_files(self):
        if not self._selected_items:
            return False

        for item in self._selected_items:
            self._on_unlock_file(item, refresh_toolbar=False)

        self._update_toolbar()

    def _on_sync_selected_files(self):
        if not self._selected_items:
            return False

        file_paths = [item.path for item in self._selected_items]
        artellapipe.FilesMgr().sync_files(file_paths)

        if len(file_paths) > 1:
            message.PopupMessage.success('Files synced successfully!', parent=self)
        else:
            message.PopupMessage.success('File synced successfully!', parent=self)

        for item in self._selected_items:
            item.refresh()

        self._update_toolbar()

    def _on_upload_selected_files(self):
        if not self._selected_items:
            return False

        for item in self._selected_items:
            self._on_upload_file(item, refresh_toolbar=False)

        self._update_toolbar()


class FilesLoadingWidget(base.BaseWidget, object):

    cancelLoad = Signal()

    def __init__(self, parent=None):
        super(FilesLoadingWidget, self).__init__(parent)

    def ui(self):
        super(FilesLoadingWidget, self).ui()

        self._cancel_btn = buttons.BaseToolButton().image('delete').icon_only()
        circle_layout = QHBoxLayout()
        circle_layout.setSpacing(2)
        circle_layout.setContentsMargins(2, 2, 2, 2)
        loading_circle = loading.CircleLoading(size=100)
        circle_layout.addStretch()
        circle_layout.addWidget(loading_circle)
        circle_layout.addStretch()
        self._progress_bar = progressbar.BaseProgressBar()
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setVisible(False)

        btn_lyt = QHBoxLayout()
        btn_lyt.setContentsMargins(0, 0, 0, 0)
        btn_lyt.setSpacing(0)
        btn_lyt.addStretch()
        btn_lyt.addWidget(self._cancel_btn)
        self.main_layout.addLayout(btn_lyt)
        self.main_layout.addStretch()
        self.main_layout.addLayout(circle_layout)
        self.main_layout.addWidget(self._progress_bar)
        self.main_layout.addStretch()

    def setup_signals(self):
        self._cancel_btn.clicked.connect(self.cancelLoad.emit)

    def set_total_files(self, total_files):
        self._progress_bar.setMinimum(0)
        self._progress_bar.setMaximum(total_files)
        self._progress_bar.setValue(0)

    def set_value(self, index, path):
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(index + 1)
        self._progress_bar.setFormat(path)

    def reset(self):
        self._progress_bar.reset()
        self._progress_bar.setValue(0)
        self._progress_bar.setFormat('')
        self._progress_bar.setVisible(False)
