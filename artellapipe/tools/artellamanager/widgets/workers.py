#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains Artella workers used by Artella Manager
"""

from __future__ import print_function, division, absolute_import

import os

from Qt.QtCore import *

from tpDcc.libs.python import folder

from artellapipe.libs.artella.core import artellalib, artellaclasses


class GetArtellaDirsWorker(QObject, object):

    dirsUpdated = Signal()

    def __init__(self, project):
        self._path = None
        self._abort = False
        self._project = project
        super(GetArtellaDirsWorker, self).__init__()

    def set_path(self, path):
        self._path = path

    def abort(self):
        self._abort = True

    def process(self):
        if not self._path:
            return

        self._abort = False

        if self._abort or not self._project:
            self.dirsUpdated.emit()
            return

        status = artellalib.get_status(self._path)
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

        self.dirsUpdated.emit()


class GetArtellaFolderStatusWorker(QObject, object):

    finished = Signal()

    def __init__(self):
        self._path = None
        self._abort = False
        self._status = None
        super(GetArtellaFolderStatusWorker, self).__init__()

    @property
    def status(self):
        return self._status

    @property
    def path(self):
        return self._path

    def set_path(self, path):
        self._path = path

    def abort(self):
        self._abort = True

    def process(self):
        if not self._path:
            return

        self._abort = False
        self._status = None

        if self._abort:
            return

        self._status = artellalib.get_status(self._path)
        self.finished.emit()


class GetArtellaFilesWorker(QObject, object):

    progressStarted = Signal(int)
    progressTick = Signal(int, str, object)
    progressDone = Signal()
    progressAbort = Signal()

    def __init__(self):
        self._paths = None
        self._abort = False

        super(GetArtellaFilesWorker, self).__init__()

    def set_paths(self, paths):
        self._paths = paths

    def abort(self):
        self._abort = True

    def process(self):
        if not self._paths:
            return

        self._abort = False
        self.progressStarted.emit(len(self._paths))

        if self._abort:
            self.progressDone.emit()
            return

        for i, path in enumerate(self._paths):
            if self._abort:
                self.progressAbort.emit()
                return
            status = artellalib.get_status(path)
            self.progressTick.emit(i, path, status)

        self.progressDone.emit()


class ArtellaCheckWorker(QObject, object):

    artellaAvailable = Signal(bool)
    finished = Signal()

    def __init__(self):
        self._abort = False
        self._metadata = None

        super(ArtellaCheckWorker, self).__init__()

    @property
    def metadata(self):
        return self._metadata

    def abort(self):
        self._abort = True

    def process(self):

        self._abort = False
        if self._abort:
            self.finished.emit()

        self._metadata = artellalib.get_metadata()
        if self._metadata is not None:
            self.artellaAvailable.emit(True)
        else:
            self.artellaAvailable.emit(False)

        self.finished.emit()
