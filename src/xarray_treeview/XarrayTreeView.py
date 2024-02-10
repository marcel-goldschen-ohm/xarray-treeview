""" Tree view of a XarrayTreeModel with context menu and mouse wheel expand/collapse.
"""

from __future__ import annotations
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import xarray as xr
from datatree import DataTree
from pyqt_ext import AbstractTreeView, KeyValueTreeItem, KeyValueTreeModel, KeyValueTreeView
from xarray_treeview import XarrayTreeItem, XarrayTreeModel


class XarrayTreeView(AbstractTreeView):

    def __init__(self, parent: QObject = None) -> None:
        AbstractTreeView.__init__(self, parent)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self._showVarsAction = QAction('Show Vars')
        self._showVarsAction.setCheckable(True)
        self._showVarsAction.setChecked(True)
        self._showVarsAction.triggered.connect(self.updateModelAndView)

        self._showCoordsAction = QAction('Show Coords')
        self._showCoordsAction.setCheckable(True)
        self._showCoordsAction.setChecked(True)
        self._showCoordsAction.triggered.connect(self.updateModelAndView)

        # store/restore fold/selection state
        self._state = {}
    
    def contextMenu(self, index: QModelIndex = QModelIndex()) -> QMenu:
        menu: QMenu = AbstractTreeView.contextMenu(self, index)
        model: XarrayTreeModel = self.model()
        menu.addSeparator()
        menu.addAction(self._showVarsAction)
        menu.addAction(self._showCoordsAction)
        menu.addAction(model._show_details_column_action)
        if not index.isValid():
            return menu
        
        item: XarrayTreeItem = model.itemFromIndex(index)
        itemPath = item.path
        if len(itemPath) > 50:
            itemPath = '...' + itemPath[-47:]

        itemMenu = QMenu(itemPath)
        itemMenu.addAction('Attrs', lambda self=self, item=item: self.editItemAttrs(item))
        itemMenu.addSeparator()
        itemMenu.addAction('Info', lambda self=self, item=item: self.popupItemInfo(item))
        
        if not item.isRoot():
            itemMenu.addSeparator()
            itemMenu.addAction('Delete', lambda self=self, item=item: self.askToDeleteItem(item))

        menu.insertSeparator(menu.actions()[0])
        menu.insertMenu(menu.actions()[0], itemMenu)

        return menu
    
    def updateModelAndView(self):
        self.storeState()
        options = {
            'show_vars': self._showVarsAction.isChecked(),
            'show_coords': self._showCoordsAction.isChecked(),
        }
        model: XarrayTreeModel = self.model()
        root: XarrayTreeItem = model.root()
        model.setRoot(XarrayTreeItem(node=root.node, key=None, options=options))
        self.restoreState()
    
    def setRoot(self, dt: DataTree):
        model: XarrayTreeModel = self.model()
        if model is None:
            return
        self.storeState()
        options = {
            'show_vars': self._showVarsAction.isChecked(),
            'show_coords': self._showCoordsAction.isChecked(),
        }
        model.setRoot(XarrayTreeItem(node=dt, key=None, options=options))
        self.restoreState()
    
    def storeState(self):
        model: XarrayTreeModel = self.model()
        if model is None:
            return
        selected: list[QModelIndex] = self.selectionModel().selectedIndexes()
        for item in model.root().depth_first():
            if item is model.root():
                continue
            index: QModelIndex = model.createIndex(item.sibling_index, 0, item)
            path = item.path
            self._state[path] = {
                'expanded': self.isExpanded(index),
                'selected': index in selected
            }

    def restoreState(self):
        model: XarrayTreeModel = self.model()
        if model is None:
            return
        self.selectionModel().clearSelection()
        selection: QItemSelection = QItemSelection()
        for item in model.root().depth_first():
            if item is model.root():
                continue
            try:
                index: QModelIndex = model.createIndex(item.sibling_index, 0, item)
                path = item.path
                self.setExpanded(index, self._state[path]['expanded'])
                if self._state[path]['selected']:
                    selection.merge(QItemSelection(index, index), QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
            except KeyError:
                self.setExpanded(index, False)
        if selection.count():
            self.selectionModel().select(selection, QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Rows)
    
    def selectedItems(self) -> list[XarrayTreeItem]:
        model: XarrayTreeModel = self.model()
        if model is None:
            return []
        selected: list[QModelIndex] = self.selectionModel().selectedRows()
        items: list[XarrayTreeItem] = [model.itemFromIndex(index) for index in selected]
        return items
    
    def editItemAttrs(self, item: XarrayTreeItem):
        if item.is_dataset():
            attrs = item.node.ds.attrs.copy()
        elif item.is_var() or item.is_coord():
            attrs = item.node.ds[item.key].attrs.copy()
        else:
            return
        
        root = KeyValueTreeItem('/', attrs)
        model = KeyValueTreeModel(root)
        view = KeyValueTreeView()
        view.setModel(model)
        view.expandAll()
        view.resizeAllColumnsToContents()

        dlg = QDialog(self)
        dlg.setWindowTitle(item.path)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(view)

        btns = QDialogButtonBox()
        btns.setStandardButtons(QDialogButtonBox.Cancel | QDialogButtonBox.Ok)
        btns.accepted.connect(dlg.accept)
        btns.rejected.connect(dlg.reject)
        layout.addWidget(btns)
        
        dlg.setWindowModality(Qt.ApplicationModal)
        dlg.setMinimumSize(QSize(400, 400))
        if dlg.exec() != QDialog.Accepted:
            return
        
        attrs = model.root().value
        if item.is_dataset():
            item.node.attrs = attrs
            # ds = item.node.to_dataset()
            # ds.attrs = attrs
            # item.node.ds = ds
        elif item.is_var() or item.is_coord():
            item.node[item.key].attrs = attrs
    
    def popupItemInfo(self, item: XarrayTreeItem):
        if item.is_dataset():
            text = str(item.node.ds)
        elif item.is_var() or item.is_coord():
            text = str(item.node.ds[item.key])
        else:
            return
        
        textEdit = QTextEdit()
        textEdit.setPlainText(text)
        textEdit.setReadOnly(True)

        dlg = QDialog(self)
        dlg.setWindowTitle(item.path)
        layout = QVBoxLayout(dlg)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(textEdit)
        dlg.exec()
    
    def askToRemoveItem(self, item: XarrayTreeItem):
        if item.is_root():
            return
        itemPath = item.path
        if len(itemPath) > 50:
            itemPath = '...' + itemPath[-47:]
        answer = QMessageBox.question(self, 'Delete', f'Delete {itemPath}?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            model: XarrayTreeModel = self.model()
            model.removeItem(item)


def test_live():
    import numpy as np
    from xarray_treeview import XarrayDndTreeModel
    app = QApplication()

    raw_ds = xr.Dataset(
        data_vars={
            'current': (['series', 'sweep', 'time'], np.random.rand(3, 10, 100) * 1e-9, {'units': 'A'}),
            'voltage': (['series', 'sweep', 'time'], np.random.rand(3, 10, 100) * 10000, {'units': 'V'}),
        },
        coords={
            'time': ('time', np.arange(100) * 0.01, {'units': 's'}),
        },
    )
    # print('-----\n raw_ds', raw_ds)

    baselined_ds = xr.Dataset(
        data_vars={
            'current': (['series', 'sweep', 'time'], np.random.rand(3, 10, 100) * 1e-9, {'units': 'A'}),
        },
    )
    # print('-----\n baselined_ds', baselined_ds)

    scaled_ds = xr.Dataset(
        data_vars={
            'current': (['series', 'sweep', 'time'], np.random.rand(1, 2, 100) * 1e-9, {'units': 'A'}),
        },
        coords={
            'series': ('series', [1]),
            'sweep': ('sweep', [5,8]),
        },
    )
    # print('-----\n scaled_ds', scaled_ds)
    
    root_node = DataTree(name='root')
    raw_node = DataTree(name='raw data', data=raw_ds, parent=root_node)
    baselined_node = DataTree(name='baselined', data=baselined_ds, parent=raw_node)
    scaled_node = DataTree(name='scaled', data=scaled_ds, parent=baselined_node)
    # print('-----\n', root_node.to_datatree())

    root_item = XarrayTreeItem(root_node)
    model = XarrayDndTreeModel(root_item)
    view = XarrayTreeView()
    view.setModel(model)
    view.show()
    view.resize(QSize(600, 600))
    view.expandAll()
    view.resizeAllColumnsToContents()

    # from PySide6.QtTest import *
    # tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Fatal)

    app.exec()


if __name__ == '__main__':
    test_live()
