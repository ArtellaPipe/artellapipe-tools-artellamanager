#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
Module that contains loading widget for Artella Manager
"""

from __future__ import print_function, division, absolute_import

__author__ = "Tomas Poveda"
__license__ = "MIT"
__maintainer__ = "Tomas Poveda"
__email__ = "tpovedatd@gmail.com"

from Qt.QtCore import *
from Qt.QtWidgets import *

from tpDcc.libs.qt.core import base
from tpDcc.libs.qt.widgets import loading, buttons, progressbar


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
