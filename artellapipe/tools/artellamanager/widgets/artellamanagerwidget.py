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
import time
import webbrowser

from Qt.QtCore import *
from Qt.QtWidgets import *
from Qt.QtGui import *

import tpDcc as tp
from tpDcc.libs.python import fileio, path as path_utils
from tpDcc.libs.qt.core import base, qtutils
from tpDcc.libs.qt.widgets import stack, dividers, buttons, message, lineedit, search

import artellapipe
from artellapipe.libs.artella.core import artellalib, artellaclasses
from artellapipe.tools.artellamanager.widgets import workers, folderstree, filestree, loading


class ArtellaManagerWidget(base.BaseWidget, object):

    METADATA = None

    def __init__(self, project, parent=None):

        self._project = project
        self._selected_items = None
        self._enabled_ui = False

        self.METADATA = None

        super(ArtellaManagerWidget, self).__init__(parent=parent)

        self._thread_pool = QThreadPool()

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
        self._folders_view = folderstree.ArtellaManagerFolderView()
        folders_layout.addWidget(self._folders_search)
        folders_layout.addWidget(dividers.Divider())
        folders_layout.addWidget(self._folders_view)

        self._stack = stack.SlidingOpacityStackedWidget()

        self._loading_widget = loading.FilesLoadingWidget()

        files_widget = QWidget()
        files_layout = QVBoxLayout()
        files_layout.setContentsMargins(2, 2, 2, 2)
        files_layout.setSpacing(2)
        files_widget.setLayout(files_layout)
        self._files_search = search.SearchFindWidget()
        self._files_list = filestree.ArtellaFilesTree(self._project)
        files_layout.addWidget(self._files_search)
        files_layout.addWidget(dividers.Divider())
        files_layout.addWidget(self._files_list)

        self._stack.addWidget(files_widget)
        self._stack.addWidget(self._loading_widget)

        splitter.addWidget(folders_widget)
        splitter.addWidget(self._stack)

    def setup_signals(self):
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
        self._artella_timer.stop()
        self._folders_view.cleanup()
        self._thread_pool.waitForDone(1000)
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

                    # In Artella Enterprise, we do not need to lock a file first to upload a new version
                    if self._project.is_enterprise():
                        self._upload_btn.setEnabled(True)
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
        self._files_search.setEnabled(flag)
        self._folders_search.setEnabled(flag)
        self._folders_view.setEnabled(flag)

    def _get_item_artella_url(self, item_path):
        if not item_path:
            return ''

        if os.path.splitext(item_path)[-1]:
            item_path = os.path.dirname(item_path)

        relative_path = os.path.relpath(item_path, self._project.get_path())
        artella_url = '{}/{}'.format(self._project.get_artella_url(), relative_path)

        return artella_url

    def _setup_file_item_signals(self, item):
        item.SIGNALS.viewLocallyItem.connect(self._on_open_item_folder)
        item.SIGNALS.openArtellaItem.connect(self._on_open_item_in_artella)
        item.SIGNALS.copyFilePath.connect(self._on_copy_file_path)
        item.SIGNALS.copyArtellaFilePath.connect(self._on_copy_artella_file_path)
        item.SIGNALS.openFile.connect(self._on_open_file)
        item.SIGNALS.importFile.connect(self._on_import_file)
        item.SIGNALS.referenceFile.connect(self._on_reference_file)
        item.SIGNALS.getDepsFile.connect(self._on_get_dependencies_file)
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

                folder_status_worker = workers.GetArtellaFolderStatusWorker(item_path, include_remote=True)
                folder_status_worker.signals.statusRetrieved.connect(self._on_get_folder_status)
                self._thread_pool.start(folder_status_worker)

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

    def _on_folder_selected(self, selected, *args):
        selected_indexes = selected.indexes()
        self._folders_view.setEnabled(False)
        self._on_refresh_selected_folder(selected_indexes)

    def _on_get_folder_status(self, status, path):
        self._files_list.clear()
        self._stack.setCurrentIndex(0)

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
        if hasattr(artellapipe, 'project') and artellapipe.project:
            if artellapipe.project.is_enterprise():
                for handle, data in status.items():
                    local_info = data.get('local_info', dict())
                    remote_info = data.get('remote_info', dict())
                    if local_info:
                        signature = local_info.get('signature', None)
                        is_folder = local_info.get('is_folder', False)
                        if is_folder or signature == 'folder':
                            continue
                        dir_path = local_info.get('path', None)
                        if dir_path and os.path.normpath(dir_path) != os.path.dirname(path):
                            all_files.append(os.path.normpath(dir_path))
                    else:
                        signature = remote_info.get('signature', '')
                        name = remote_info.get('name', '')
                        if not signature or signature == 'folder' or not name:
                            continue
                        if os.path.normpath(os.path.join(
                                os.path.dirname(path), name)) == os.path.normpath(path):
                            continue
                        dir_path = os.path.join(path, name)
                        all_files.append(os.path.normpath(dir_path))
            else:
                if isinstance(status, artellaclasses.ArtellaDirectoryMetaData):
                    for ref_name, ref_data in status.references.items():
                        dir_path = ref_data.path
                        if ref_data.deleted or ref_data.maximum_version_deleted or os.path.isdir(
                                dir_path) or not os.path.splitext(dir_path)[-1]:
                            continue
                        all_files.append(dir_path)
                else:
                    all_files.append(path)

        if not all_files:
            self._folders_view.setEnabled(True)

        artella_files_worker = workers.GetArtellaFilesWorker(all_files, include_remote=True)
        artella_files_worker.signals.progressStarted.connect(self._on_start_find_files)
        artella_files_worker.signals.progressTick.connect(self._on_update_find_files)
        artella_files_worker.signals.progressAbort.connect(self._on_abort_find_files)
        artella_files_worker.signals.progressDone.connect(self._on_done_find_files)
        self._thread_pool.start(artella_files_worker)

    def _on_check_finished(self):
        self._check_artella_worker.moveToThread(QThread.currentThread())
        self.METADATA = self._check_artella_worker._metadata
        self._check_artella_worker.deleteLater()

    def _on_update_metadata(self):
        artella_check_worker = workers.ArtellaCheckWorker()
        artella_check_worker.signals.artellaAvailable.connect(self._on_artella_checked)
        self._thread_pool.start(artella_check_worker)

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
                        list_item = filestree.ArtellaFileItem(project=self._project, path=folder_file_path)
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
            list_item = filestree.ArtellaFileItem(
                project=self._project, path=path, status=status, metadata=self.METADATA)
            if list_item.is_directory or list_item.is_deleted:
                return
            self._setup_file_item_signals(list_item)
            self._files_list.addTopLevelItem(list_item)

    def _on_open_item_in_artella(self, item_path):
        if not item_path:
            return

        artella_url = self._get_item_artella_url(item_path)
        if not artella_url:
            return

        webbrowser.open(artella_url)

    def _on_open_item_folder(self, item_path):
        if os.path.splitext(item_path)[-1]:
            fileio.open_browser(os.path.dirname(item_path))
        else:
            fileio.open_browser(item_path)

    def _on_open_file(self, item_path):
        res = qtutils.show_question(self, 'Opening File', 'Are you sure you want to open the file?')
        if res == QMessageBox.StandardButton.Yes:
            return tp.Dcc.open_file(item_path)

    def _on_import_file(self, item_path):
        res = qtutils.show_question(self, 'Importing File', 'Are you sure you want to import the file?')
        if res == QMessageBox.StandardButton.Yes:
            return tp.Dcc.import_file(item_path, force=True)

    def _on_reference_file(self, item_path):
        res = qtutils.show_question(self, 'Referencing File', 'Are you sure you want to reference the file?')
        if res == QMessageBox.StandardButton.Yes:
            return tp.Dcc.reference_file(item_path, force=True)

    def _on_get_dependencies_file(self, item_path):
        res = qtutils.show_question(self, 'Get File Dependencies', 'Are you sure you want to get file dependencies?')
        if res == QMessageBox.StandardButton.Yes:
            artellapipe.ToolsMgr().run_tool(
                'artellapipe-tools-dependenciesmanager', do_reload=True, debug=False, file_path=item_path)

    def _on_lock_file(self, item, refresh_toolbar=True):
        if not self._project:
            return

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

        # We wait some seconds before checking lock status again, otherwise Artella server won't return a valid value
        if self._project.is_enterprise():
            time.sleep(2.0)

        item.refresh()

        if refresh_toolbar:
            self._update_toolbar()

    def _on_copy_file_path(self, item_path):
        if not item_path:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(item_path, QClipboard.Clipboard)
        if clipboard.supportsSelection():
            clipboard.setText(item_path, QClipboard.Selection)
        message.PopupMessage.success(text='File path copied to clipboard!.', parent=self)

    def _on_copy_artella_file_path(self, item_path):
        if not item_path:
            return

        artella_url = self._get_item_artella_url(item_path)
        if not artella_url:
            return

        clipboard = QApplication.clipboard()
        clipboard.setText(artella_url, QClipboard.Clipboard)
        if clipboard.supportsSelection():
            clipboard.setText(artella_url, QClipboard.Selection)
        message.PopupMessage.success(text='File Artella path copied to clipboard!.', parent=self)

    def _on_unlock_file(self, item, refresh_toolbar=True):

        if not self._project:
            return

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

        # We wait some seconds before checking lock status again, otherwise Artella server won't return a valid value
        if self._project.is_enterprise():
            time.sleep(2.0)

        item.refresh()

        if refresh_toolbar:
            self._update_toolbar()

    def _on_sync_file(self, item):

        if not self._project:
            return

        item_path = item.path
        artellapipe.FilesMgr().sync_files([item_path])

        message.PopupMessage.success('File synced successfully!', parent=self)

        # We wait some seconds before checking lock status again, otherwise Artella server won't return a valid value
        if self._project.is_enterprise():
            time.sleep(2.0)

        item.refresh()

        self._update_toolbar()

    def _on_upload_file(self, item, refresh_toolbar=True):

        if not self._project:
            return

        item_path = item.path
        valid_version = artellapipe.FilesMgr().upload_working_version(item_path)

        if valid_version:
            message.PopupMessage.success('File version uploaded successfully!', parent=self)

        # We wait some seconds before checking lock status again, otherwise Artella server won't return a valid value
        if self._project.is_enterprise():
            time.sleep(2.0)

        item.refresh()

        if refresh_toolbar:
            self._update_toolbar()

    def _on_lock_selected_files(self):
        if not self._project:
            return False

        if not self._selected_items:
            return False

        for item in self._selected_items:
            self._on_lock_file(item, refresh_toolbar=False)

        self._update_toolbar()

    def _on_unlock_selected_files(self):
        if not self._project:
            return

        if not self._selected_items:
            return False

        for item in self._selected_items:
            self._on_unlock_file(item, refresh_toolbar=False)

        self._update_toolbar()

    def _on_sync_selected_files(self):
        if not self._project:
            return

        if not self._selected_items:
            return False

        file_paths = [item.path for item in self._selected_items]
        artellapipe.FilesMgr().sync_files(file_paths)

        if len(file_paths) > 1:
            message.PopupMessage.success('Files synced successfully!', parent=self)
        else:
            message.PopupMessage.success('File synced successfully!', parent=self)

        # We wait some seconds before checking lock status again, otherwise Artella server won't return a valid value
        if self._project.is_enterprise():
            time.sleep(2.0)

        for item in self._selected_items:
            item.refresh()

        self._update_toolbar()

    def _on_upload_selected_files(self):
        if not self._project:
            return

        if not self._selected_items:
            return False

        for item in self._selected_items:
            self._on_upload_file(item, refresh_toolbar=False)

        self._update_toolbar()
