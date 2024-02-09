""" Tree model that uses XarrayTreeItem for its data interface.
"""

from __future__ import annotations
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import qtawesome as qta
import xarray as xr
from pyqt_ext import AbstractTreeModel
from xarray_treeview import XarrayTreeItem


class XarrayTreeModel(AbstractTreeModel):
    
    def __init__(self, root: XarrayTreeItem, parent: QObject = None):
        AbstractTreeModel.__init__(self, root, parent)
        self.setColumnLabels(['Data', 'Details'])

        # allowed selections
        self._allowed_selections = ['dataset', 'var', 'coord']

        # column 1 = details column
        self._show_details_column = True
        self._show_details_column_action = QAction('Show Details Column')
        self._show_details_column_action.setCheckable(True)
        self._show_details_column_action.setChecked(True)
        self._show_details_column_action.triggered.connect(self.setShowDetailsColumn)

        # # var/coord names shared amongst all datasets in tree?
        # self._share_var_names = True
    
    def allowedSelections(self) -> list[str]:
        return self._allowed_selections
    
    def setAllowedSelections(self, selections: list[str]) -> None:
        self._allowed_selections = selections
    
    def showDetailsColumn(self) -> bool:
        return self._show_details_column
    
    def setShowDetailsColumn(self, show: bool) -> None:
        if self._show_details_column == show:
            return
        if show:
            self.beginInsertColumns(QModelIndex(), 1, 1)
            self._show_details_column = True
            self.endInsertColumns()
        else:
            self.beginRemoveColumns(QModelIndex(), 1, 1)
            self._show_details_column = False
            self.endRemoveColumns()
        self._show_details_column_action.setChecked(show)
    
    # def shareVarNames(self) -> bool:
    #     return self._share_var_names
    
    # def setShareVarNames(self, share: bool) -> None:
    #     self._share_var_names = share
    
    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if self.showDetailsColumn():
            return 2
        return 1

    def flags(self, index: QModelIndex) -> Qt.ItemFlag:
        if not index.isValid():
            if self.supportedDropActions() != Qt.DropAction.IgnoreAction:
                # allow drops on the root item (i.e., this allows drops on the viewport away from other items)
                return Qt.ItemFlag.ItemIsDropEnabled
            return Qt.ItemFlag.NoItemFlags
        item: XarrayTreeItem = self.itemFromIndex(index)
        if index.column() == 0:
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
        elif index.column() == 1:
            # cannot edit details column
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        # drag and drop
        if self.supportedDropActions() != Qt.DropAction.IgnoreAction:
            flags |= Qt.ItemFlag.ItemIsDragEnabled
            if item.is_dataset():
                flags |= Qt.ItemFlag.ItemIsDropEnabled
        return flags

    def data(self, index: QModelIndex, role: int):
        if not index.isValid():
            return
        item: XarrayTreeItem = self.itemFromIndex(index)
        if role == Qt.ItemDataRole.DisplayRole or role == Qt.ItemDataRole.EditRole:
            return item.data(index.column())
        elif role == Qt.ItemDataRole.DecorationRole:
            if index.column() == 0:
                if item.is_var():
                    return qta.icon('ph.cube-thin')
                if item.is_coord():
                    return qta.icon('ph.list-numbers-thin')

    def setData(self, index: QModelIndex, value, role: int) -> bool:
        item: XarrayTreeItem = self.itemFromIndex(index)
        if role == Qt.ItemDataRole.EditRole:
            if index.column() == 0:
                if value == item.key:
                    return False
                if (item.is_var() or item.is_coord()):
                    answer = QMessageBox.question(None, 'Rename throughout tree?', f'Rename {item.key} to {value} throughout tree?', QMessageBox.Yes | QMessageBox.No)
                    if answer == QMessageBox.Yes:
                        # check that all name changes in tree are valid
                        # and get list of all items needing a name change
                        items_to_rename: list[XarrayTreeItem] = []
                        for _item in item.root.depth_first():
                            if _item.key == item.key:
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
    
    # def moveRow(self, sourceParent: QModelIndex, sourceRow: int, destinationParent: QModelIndex, destinationRow: int) -> bool:
    #     if sourceParent == destinationParent:
    #         return False
    #     if sourceRow < 0 or sourceRow >= self.rowCount(sourceParent):
    #         return False
    #     if destinationRow < 0:
    #         # negative indexing
    #         destinationRow += self.rowCount(destinationParent)
    #     if destinationRow < 0 or destinationRow > self.rowCount(destinationParent):
    #         return False

    #     source_parent_item: XarrayTreeItem = self.get_item(sourceParent)
    #     source_item: XarrayTreeItem = source_parent_item.children[sourceRow]
    #     destination_parent_item: XarrayTreeItem = self.get_item(destinationParent)
        
    #     # try to move
    #     success: bool = False
    #     self.beginMoveRows(sourceParent, sourceRow, sourceRow, destinationParent, destinationRow)
    #     try:
    #         source_item.set_parent(destination_parent_item)
    #         success = True
    #     except:
    #         success = False
    #     # if source_item.is_dataset():
    #     #     try:
    #     #         source_item.node.parent = destination_parent_item.node
    #     #         # destinationRow = destination_parent_item.children.index(source_item)
    #     #         destination_parent_item.insert_child(destinationRow, source_item)
    #     #         success = True
    #     #     except:
    #     #         pass
    #     # elif source_item.is_var():
    #     #     source_ds: xr.Dataset = source_parent_item.node.data
    #     #     destination_ds: xr.Dataset = destination_parent_item.node.data
    #     #     move_ds = xr.Dataset(data_vars={source_item.key: source_ds.data_vars[source_item.key]})
    #     #     try:
    #     #         destination_parent_item.node.data = xr.merge([destination_ds, move_ds])
    #     #         source_parent_item.node.data = source_ds.drop_vars(source_item.key)
    #     #         destination_parent_item.insert_child(destinationRow, source_item)
    #     #         success = True
    #     #     except:
    #     #         # TODO: ask before combining with lossy merge
    #     #         try:
    #     #             destination_parent_item.node.data = move_ds.combine_first(destination_ds)
    #     #             source_parent_item.node.data = source_ds.drop_vars(source_item.key)
    #     #             destination_parent_item.insert_child(destinationRow, source_item)
    #     #             success = True
    #     #         except:
    #     #             pass
    #     # elif source_item.is_coord():
    #     #     pass
    #     self.endMoveRows()
    #     return success
    

class XarrayDndTreeModel(XarrayTreeModel):

    def __init__(self, root: XarrayTreeItem = None, parent: QObject = None):
        XarrayTreeModel.__init__(self, root, parent)
    
    def supportedDropActions(self) -> Qt.DropActions:
        return Qt.DropAction.MoveAction | Qt.DropAction.CopyAction