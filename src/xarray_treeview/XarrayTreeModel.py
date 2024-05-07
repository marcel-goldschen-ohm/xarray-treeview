""" Tree model that uses XarrayTreeItem for its data interface.
"""

from __future__ import annotations
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import qtawesome as qta
import xarray as xr
from pyqt_ext.tree import AbstractTreeModel
from xarray_treeview import XarrayTreeItem


class XarrayTreeModel(AbstractTreeModel):
    
    def __init__(self, root: XarrayTreeItem, parent: QObject = None):
        AbstractTreeModel.__init__(self, root, parent)
        self.setColumnLabels(['Data', 'Details'])

        # allowed selections
        self._allowedSelections = ['node', 'var', 'coord']

        # column 1 = details column
        self._showDetailsColumn = True
        self._showDetailsColumnAction = QAction('Show Details Column')
        self._showDetailsColumnAction.setCheckable(True)
        self._showDetailsColumnAction.setChecked(True)
        self._showDetailsColumnAction.triggered.connect(self.setShowDetailsColumn)
    
    def allowedSelections(self) -> list[str]:
        return self._allowedSelections
    
    def setAllowedSelections(self, selections: list[str]) -> None:
        self._allowedSelections = selections
    
    def showDetailsColumn(self) -> bool:
        return self._showDetailsColumn
    
    def setShowDetailsColumn(self, show: bool) -> None:
        if self._showDetailsColumn == show:
            return
        if show:
            self.beginInsertColumns(QModelIndex(), 1, 1)
            self._showDetailsColumn = True
            self.endInsertColumns()
        else:
            self.beginRemoveColumns(QModelIndex(), 1, 1)
            self._showDetailsColumn = False
            self.endRemoveColumns()
        self._showDetailsColumnAction.setChecked(show)
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if self.showDetailsColumn():
            return 2
        return 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            # root item
            if self.supportedDropActions() != Qt.DropAction.IgnoreAction:
                # allow drops on the root item (i.e., this allows drops on the viewport away from other items)
                return Qt.ItemFlag.ItemIsDropEnabled
            return Qt.ItemFlag.NoItemFlags
        item: XarrayTreeItem = self.itemFromIndex(index)
        if index.column() == 0:
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsEditable
        elif index.column() == 1:
            # cannot edit details column
            flags = Qt.ItemFlag.ItemIsEnabled
        if item.is_node() and 'node' in self.allowedSelections():
            flags |= Qt.ItemFlag.ItemIsSelectable
        elif item.is_var() and 'var' in self.allowedSelections():
            flags |= Qt.ItemFlag.ItemIsSelectable
        elif item.is_coord() and 'coord' in self.allowedSelections():
            flags |= Qt.ItemFlag.ItemIsSelectable
        # drag and drop
        if self.supportedDropActions() != Qt.DropAction.IgnoreAction:
            flags |= Qt.ItemFlag.ItemIsDragEnabled
            if item.is_node():
                # can only drop on node items
                flags |= Qt.ItemFlag.ItemIsDropEnabled
        return flags

    def data(self, index: QModelIndex, role: int):
        if not index.isValid():
            return
        item: XarrayTreeItem = self.itemFromIndex(index)
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return item.get_data(index.column())
        if role == Qt.ItemDataRole.DecorationRole:
            if index.column() == 0:
                if item.is_node():
                    return qta.icon('ph.folder-thin')
                if item.is_var():
                    return qta.icon('ph.cube-thin')
                if item.is_coord():
                    return qta.icon('ph.list-numbers-thin')

    def setData(self, index: QModelIndex, value, role: int) -> bool:
        item: XarrayTreeItem = self.itemFromIndex(index)
        if role == Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                if item.is_var() or item.is_coord():
                    answer = QMessageBox.question(
                        None, 'Rename throughout tree?', f'Rename {item.key} to {value} throughout tree?', 
                        buttons = QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, defaultButton = QMessageBox.StandardButton.Yes
                    )
                    if answer == QMessageBox.StandardButton.Yes:
                        # check that all name changes in tree are valid
                        # and get list of all items needing a name change
                        items_to_rename: list[XarrayTreeItem] = []
                        for _item in self.root().depth_first():
                            if (_item.is_var() or _item.is_coord()) and (_item.key == item.key):
                                if value in _item.node.ds:
                                    # name already exists
                                    QMessageBox.warning(None, 'Name already exists', f'Name {value} already exists in dataset {_item.node.name}.')
                                    return False
                                items_to_rename.append(_item)
                        for _item in items_to_rename:
                            success: bool = _item.set_data(0, value)
                            if success:
                                _index: QModelIndex = self.createIndex(_item.sibling_index, 0, _item)
                                self.dataChanged.emit(_index, _index)
                        return True
            success: bool = item.set_data(index.column(), value)
            return success
        return False
    

class XarrayDndTreeModel(XarrayTreeModel):

    def __init__(self, root: XarrayTreeItem = None, parent: QObject = None):
        XarrayTreeModel.__init__(self, root, parent)
    
    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction