""" Tree view of a XarrayTreeModel with context menu and mouse wheel expand/collapse.
"""

from __future__ import annotations
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import xarray as xr
from datatree import DataTree
from pyqt_ext.tree import TreeView, KeyValueTreeItem, KeyValueTreeModel, KeyValueTreeView
from xarray_treeview import XarrayTreeItem, XarrayTreeModel


class XarrayTreeView(TreeView):

    finishedEditingAttrs = Signal()

    def __init__(self, parent: QObject = None) -> None:
        TreeView.__init__(self, parent)

        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self._showVarsAction = QAction('Show Vars')
        self._showVarsAction.setCheckable(True)
        self._showVarsAction.setChecked(True)
        self._showVarsAction.triggered.connect(self.updateTree)

        self._showCoordsAction = QAction('Show Coords')
        self._showCoordsAction.setCheckable(True)
        self._showCoordsAction.setChecked(True)
        self._showCoordsAction.triggered.connect(self.updateTree)
    
    def setModel(self, model: XarrayTreeModel):
        root: XarrayTreeItem = model.root()
        if root is not None:
            options = {
                'show_vars': self._showVarsAction.isChecked(),
                'show_coords': self._showCoordsAction.isChecked(),
            }
            model.setRoot(XarrayTreeItem(node=root.node, key=None, options=options))
        TreeView.setModel(self, model)
    
    def setTree(self, dt: DataTree):
        self.storeState()
        options = {
            'show_vars': self._showVarsAction.isChecked(),
            'show_coords': self._showCoordsAction.isChecked(),
        }
        root: XarrayTreeItem = XarrayTreeItem(dt, options=options)
        model: XarrayTreeModel = self.model()
        if model is None:
            model = XarrayTreeModel(root)
            self.setModel(model)
        else:
            model.setRoot(root)
        self.restoreState()
    
    def updateTree(self):
        model: XarrayTreeModel = self.model()
        if model is None:
            return
        root: XarrayTreeItem = model.root()
        if root is None:
            return
        options = {
            'show_vars': self._showVarsAction.isChecked(),
            'show_coords': self._showCoordsAction.isChecked(),
        }
        self.storeState()
        model.setRoot(XarrayTreeItem(node=root.node, key=None, options=options))
        self.restoreState()
    
    def isShowVars(self) -> bool:
        return self._showVarsAction.isChecked()
    
    def setShowVars(self, show: bool):
        self._showVarsAction.setChecked(show)
        self.updateTree()
    
    def isShowCoords(self) -> bool:
        return self._showCoordsAction.isChecked()
    
    def setShowCoords(self, show: bool):
        self._showCoordsAction.setChecked(show)
        self.updateTree()
    
    def contextMenu(self, index: QModelIndex = QModelIndex()) -> QMenu:
        menu: QMenu = TreeView.contextMenu(self, index)
        model: XarrayTreeModel = self.model()
        menu.addSeparator()
        menu.addAction(self._showVarsAction)
        menu.addAction(self._showCoordsAction)
        menu.addAction(model._showDetailsColumnAction)
        if not index.isValid():
            return menu
        
        item: XarrayTreeItem = model.itemFromIndex(index)
        itemPath = item.path
        if len(itemPath) > 50:
            itemPath = '...' + itemPath[-47:]

        itemMenu = QMenu(itemPath)
        itemMenu.addAction('Info', lambda self=self, item=item: self.popupItemInfo(item))
        itemMenu.addSeparator()
        itemMenu.addAction('Attrs', lambda self=self, item=item: self.editItemAttrs(item))
        
        if not item.is_root():
            itemMenu.addSeparator()
            itemMenu.addAction('Delete', lambda self=self, item=item, label=itemPath: self.askToRemoveItem(item, label))

        menu.insertSeparator(menu.actions()[0])
        menu.insertMenu(menu.actions()[0], itemMenu)

        return menu
    
    def editItemAttrs(self, item: XarrayTreeItem):
        if item.is_node():
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
        if item.is_node():
            item.node.attrs = attrs
        elif item.is_var() or item.is_coord():
            item.node[item.key].attrs = attrs
        
        self.finishedEditingAttrs.emit()
    
    def popupItemInfo(self, item: XarrayTreeItem):
        if item.is_node():
            text = str(item.node.ds)
        elif item.is_var() or item.is_coord():
            text = str(item.node[item.key])
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
    raw_node = DataTree(name='raw', data=raw_ds, parent=root_node)
    baselined_node = DataTree(name='baselined', data=baselined_ds, parent=raw_node)
    scaled_node = DataTree(name='scaled', data=scaled_ds, parent=baselined_node)
    # print('-----\n', root_node.to_datatree())

    root_item = XarrayTreeItem(root_node)
    model = XarrayDndTreeModel(root_item)
    view = XarrayTreeView()
    view.setSelectionMode(QAbstractItemView.ExtendedSelection)
    view.setModel(model)
    view.show()
    view.resize(QSize(600, 600))
    view.expandAll()
    view.resizeAllColumnsToContents()

    app.exec()


if __name__ == '__main__':
    test_live()
