#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Artella workers used by Artella Manager
"""

from __future__ import print_function, division, absolute_import

import os

from Qt.QtCore import *

from tpDcc.libs.python import python

from artellapipe.libs.artella.core import artellalib, artellaclasses


class GetArtellaDirsWorkerSignals(QObject, object):
    dirsUpdated = Signal(list, list)
    publishedDirsUpdated = Signal(list)


class GetArtellaDirsWorker(QRunnable, object):

    def __init__(self, path, project):
        self._path = path
        self._project = project
        self.signals = GetArtellaDirsWorkerSignals()
        super(GetArtellaDirsWorker, self).__init__()

    def run(self):
        folders_found = list()
        folders_delete = list()

        if not self._project:
            self.signals.dirsUpdated.emit(folders_found, folders_delete)
            return

        folders_found, folders_delete = self._run_enterprise() if self._project.is_enterprise() else self._run_indie()

        return folders_found, folders_delete

    def _run_enterprise(self):
        """
        Internal function that downloads available folders in given path for Artella Indie
        :param status: dict
        """

        status = artellalib.get_status(self._path, include_remote=True)

        folders_found = list()
        folders_to_delete = list()
        if not status:
            return folders_found

        for handle, status_data in status.items():
            if 'local_info' not in status_data:
                continue
            local_info = status_data.get('local_info', dict())
            remote_info = status_data.get('remote_info', dict())

            remote_raw_info = remote_info.get('raw', dict())
            is_deleted = remote_raw_info.get('deleted', False)
            is_invalid = remote_raw_info.get('invalid', False)
            signature = local_info.get('signature', '')
            folder_path = local_info.get('path', '')

            if is_deleted or is_invalid:
                if folder_path and os.path.isdir(folder_path):
                    folders_to_delete.append(folder_path)
                continue

            if not signature or not folder_path:
                name = remote_info.get('name', '')
                signature = remote_info.get('signature', '')
                folder_path = os.path.join(self._path, name)

            if (not signature or signature != 'folder') or not folder_path:
                continue
            if os.path.normpath(self._path) == os.path.normpath(folder_path):
                continue

            folders_found.append(folder_path)

        self.signals.dirsUpdated.emit(folders_found, folders_to_delete)

        return folders_found, folders_to_delete

    def _run_indie(self):
        """
        Internal function that downloads available folders in given path for Artella Indie
        :param status: artellaclasses
        """

        status = artellalib.get_status(self._path)

        folders_found = list()
        folders_to_delete = list()

        is_asset = False
        if isinstance(status, artellaclasses.ArtellaDirectoryMetaData):
            for ref_name, ref_data in status.references.items():
                dir_path = ref_data.path
                if ref_data.deleted or ref_data.maximum_version_deleted or os.path.isdir(
                        dir_path) or os.path.splitext(dir_path)[-1]:
                    continue
                folders_found.append(dir_path)
        elif isinstance(status, artellaclasses.ArtellaAssetMetaData):
            working_folder = self._project.get_working_folder()
            working_path = os.path.join(status.path, working_folder)
            artella_data = artellalib.get_status(working_path)
            if isinstance(artella_data, artellaclasses.ArtellaDirectoryMetaData):
                folders_found.append(working_path)
            is_asset = True

        self.signals.dirsUpdated.emit(folders_found, folders_to_delete)

        if is_asset:
            published_folders_found = list()
            published_versions = status.get_published_versions(force_update=True)
            if published_versions:
                for version_name, version_data_list in published_versions.items():
                    for version_data in version_data_list:
                        version_path = version_data[2]
                        # No need to check path status because published versions function already does that
                        published_folders_found.append(version_path)
            self.signals.publishedDirsUpdated.emit(published_folders_found)

        return folders_found, folders_to_delete


class GetArtellaFolderStatusWorkerSignals(QObject, object):
    statusRetrieved = Signal(object, str)


class GetArtellaFolderStatusWorker(QRunnable, object):
    def __init__(self, path, include_remote=False):
        self._path = path
        self._include_remote = include_remote
        self.signals = GetArtellaFolderStatusWorkerSignals()
        super(GetArtellaFolderStatusWorker, self).__init__()

    def run(self):
        if not self._path:
            return

        status = artellalib.get_status(self._path, include_remote=self._include_remote)
        self.signals.statusRetrieved.emit(status, self._path)


class GetArtellaFilesWorkerSignals(QObject, object):
    progressStarted = Signal(int)
    progressTick = Signal(int, str, object)
    progressDone = Signal()
    progressAbort = Signal()


class GetArtellaFilesWorker(QRunnable, object):
    def __init__(self, paths, include_remote=False):
        self._paths = python.force_list(paths)
        self._abort = False
        self._include_remote = include_remote
        self.signals = GetArtellaFilesWorkerSignals()
        super(GetArtellaFilesWorker, self).__init__()

    def abort(self):
        self._abort = True

    def run(self):
        if not self._paths:
            return

        self._abort = False
        self.signals.progressStarted.emit(len(self._paths))

        if self._abort:
            self.signals.progressDone.emit()
            return

        for i, path in enumerate(self._paths):
            if self._abort:
                self.signals.progressAbort.emit()
                return
            status = artellalib.get_status(path, include_remote=self._include_remote)
            self.signals.progressTick.emit(i, path, status)

        self.signals.progressDone.emit()


class ArtellaCheckWorkerSignals(QObject, object):
    artellaAvailable = Signal(bool)


class ArtellaCheckWorker(QRunnable, object):
    def __init__(self):
        super(ArtellaCheckWorker, self).__init__()

        self.signals = ArtellaCheckWorkerSignals()

    def run(self):
        metadata = artellalib.get_metadata()
        if metadata is not None:
            self.signals.artellaAvailable.emit(True)
        else:
            self.signals.artellaAvailable.emit(False)
