""" Tree model that uses XarrayTreeItem for its data interface.
"""

from __future__ import annotations
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import qtawesome as qta
import xarray as xr
from pyqt_ext import AbstractTreeModel
from pyqt_xarray_treeview import XarrayTreeItem


class XarrayTreeModel(AbstractTreeModel):
    
    def __init__(self, root: XarrayTreeItem, parent: QObject = None):
        AbstractTreeModel.__init__(self, root, parent)
        self.column_labels = ['Data', 'Details']

        # var names shared amongst all datasets in tree
        self._share_var_names = True

        # allowed selections
        self._allowed_selections = ['dataset', 'var', 'coord']

        # column 1 = details column
        self._show_details_column = True
        self.show_details_column_action = QAction('Show Details Column')
        self.show_details_column_action.setCheckable(True)
        self.show_details_column_action.setChecked(True)
        self.show_details_column_action.triggered.connect(self.set_show_details_column)
    
    @property
    def show_details_column(self) -> bool:
        return self._show_details_column
    
    @show_details_column.setter
    def show_details_column(self, show_details_column: bool) -> None:
        if self._show_details_column == show_details_column:
            return
        if self.show_details_column == show_details_column:
            return
        if show_details_column:
            self.beginInsertColumns(QModelIndex(), 1, 1)
            self._show_details_column = True
            self.endInsertColumns()
        else:
            self.beginRemoveColumns(QModelIndex(), 1, 1)
            self._show_details_column = False
            self.endRemoveColumns()
        self.show_details_column_action.setChecked(show_details_column)
    
    @Slot(bool)
    def set_show_details_column(self, show_details_column: bool) -> None:
        self.show_details_column = show_details_column
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if self.show_details_column:
            return 2
        return 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        item: XarrayTreeItem = self.get_item(index)
        if item is None:
            return Qt.ItemFlag.NoItemFlags
        if item.is_node() and 'dataset' not in self._allowed_selections:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
        if item.is_var() and 'var' not in self._allowed_selections:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
        if item.is_coord() and 'coord' not in self._allowed_selections:
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
        if index.column() == 1:
            # cannot edit details column
            return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def data(self, index: QModelIndex, role: int):
        if not index.isValid():
            return
        item: XarrayTreeItem = self.get_item(index)
        if item is None:
            return
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return item.data(index.column())
        elif role == Qt.ItemDataRole.DecorationRole:
            if index.column() == 0:
                if item.is_var():
                    return qta.icon('ph.cube-thin')
                if item.is_coord():
                    return qta.icon('ph.list-numbers-thin')

    def setData(self, index: QModelIndex, value, role: int) -> bool:
        if role != Qt.ItemDataRole.EditRole:
            return False
        item: XarrayTreeItem = self.get_item(index)
        if item is None:
            return False
        if role == Qt.ItemDataRole.EditRole:
            if (item.is_var() or item.is_coord()) and self._share_var_names:
                # check that all name changes in tree are valid
                # and get list of all items needing a name change
                changed_items: list[XarrayTreeItem] = []
                _item: XarrayTreeItem = item.root()
                while _item is not None:
                    ds: xr.Dataset = _item.node.dataset
                    if ds is not None:
                        if item.is_var() and _item.is_var():
                            if value in ds.data_vars:
                                # name already exists
                                return False
                            if item.key == _item.key:
                                changed_items.append(_item)
                        elif item.is_coord() and _item.is_coord():
                            if value in ds.coords:
                                # name already exists
                                return False
                            if item.key == _item.key:
                                changed_items.append(_item)
                    _item = _item.next_item_depth_first()
                for _item in changed_items:
                    success: bool = _item.set_data(0, value)
                    if success:
                        _index: QModelIndex = self.createIndex(_item.row(), 0, _item)
                        self.dataChanged.emit(_index, _index)
                return True
            success: bool = item.set_data(index.column(), value)
            return success
        return False
