""" Tree view of a XarrayTreeModel with context menu and mouse wheel expand/collapse.
"""

from __future__ import annotations
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import xarray as xr
from pyqt_ext import AbstractTreeView, KeyValueTreeItem, KeyValueTreeModel, KeyValueTreeView
from pyqt_xarray_treeview import XarrayTreeNode, XarrayTreeItem, XarrayTreeModel


class XarrayTreeView(AbstractTreeView):

    def __init__(self, parent: QObject = None) -> None:
        AbstractTreeView.__init__(self, parent)
        self.setSelectionMode(QAbstractItemView.MultiSelection)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        self.show_vars_action = QAction('Show Vars')
        self.show_vars_action.setCheckable(True)
        self.show_vars_action.setChecked(True)
        self.show_vars_action.triggered.connect(self.update_model_and_view)

        self.show_coords_action = QAction('Show Coords')
        self.show_coords_action.setCheckable(True)
        self.show_coords_action.setChecked(True)
        self.show_coords_action.triggered.connect(self.update_model_and_view)

        # store/restore fold/selection state
        self._state = {}

        # custom context menu items
        self._custom_context_menu_actions: list[QAction] = []
    
    def contextMenu(self, index: QModelIndex = QModelIndex()) -> QMenu:
        menu: QMenu = AbstractTreeView.contextMenu(self, index)
        model: XarrayTreeModel = self.model()
        menu.addSeparator()
        menu.addAction(self.show_vars_action)
        menu.addAction(self.show_coords_action)
        menu.addAction(model.show_details_column_action)
        if not index.isValid():
            return menu
        item: XarrayTreeItem = model.get_item(index)
        if self._custom_context_menu_actions:
            menu.addSeparator()
            for action in self._custom_context_menu_actions:
                menu.addAction(action)
        menu.addSeparator()
        menu.addAction('Attrs', lambda self=self, item=item: self.edit_item_attrs(item))
        menu.addSeparator()
        menu.addAction('Info', lambda self=self, item=item: self.popup_item_info(item))
        menu.addSeparator()
        menu.addAction('Delete', lambda self=self, item=item: self.ask_to_delete_item(item))
        return menu
    
    def update_model_and_view(self):
        self.store_state()
        options = {
            'show_vars': self.show_vars_action.isChecked(),
            'show_coords': self.show_coords_action.isChecked(),
        }
        model: XarrayTreeModel = self.model()
        model.root = XarrayTreeItem(node=model.root.node, key=None, options=options)
        self.restore_state()
    
    def set_data(self, root_node: XarrayTreeNode):
        self.store_state()
        options = {
            'show_vars': self.show_vars_action.isChecked(),
            'show_coords': self.show_coords_action.isChecked(),
        }
        model: XarrayTreeModel = self.model()
        model.root = XarrayTreeItem(node=root_node, key=None, options=options)
        self.restore_state()
    
    def store_state(self):
        model: XarrayTreeModel = self.model()
        if model is None:
            return
        selected: list[QModelIndex] = self.selectionModel().selectedIndexes()
        item: XarrayTreeItem = model.root.next_item_depth_first()
        while item is not None:
            index: QModelIndex = model.createIndex(item.row(), 0, item)
            path = item.path
            self._state[path] = {
                'expanded': self.isExpanded(index),
                'selected': index in selected
            }
            item = item.next_item_depth_first()

    def restore_state(self):
        model: XarrayTreeModel = self.model()
        if model is None:
            return
        self.selectionModel().clearSelection()
        selection: QItemSelection = QItemSelection()
        item: XarrayTreeItem = model.root.next_item_depth_first()
        while item is not None:
            try:
                index: QModelIndex = model.createIndex(item.row(), 0, item)
                path = item.path
                self.setExpanded(index, self._state[path]['expanded'])
                if self._state[path]['selected']:
                    selection.merge(QItemSelection(index, index), QItemSelectionModel.Select | QItemSelectionModel.Rows)
            except KeyError:
                self.setExpanded(index, False)
            item = item.next_item_depth_first()
        if selection.count():
            self.selectionModel().select(selection, QItemSelectionModel.Select | QItemSelectionModel.Rows)
    
    def selected_items(self) -> list[XarrayTreeItem]:
        model: XarrayTreeModel = self.model()
        if model is None:
            return []
        selected: list[QModelIndex] = self.selectionModel().selectedRows()
        items: list[XarrayTreeItem] = [model.get_item(index) for index in selected]
        return items
    
    def edit_item_attrs(self, item: XarrayTreeItem):
        ds: xr.Dataset = item.node.dataset
        if ds is None:
            return
        if item.is_node():
            attrs = ds.attrs.copy()
        elif item.is_var():
            attrs = ds.data_vars[item.key].attrs.copy()
        elif item.is_coord():
            attrs = ds.coords[item.key].attrs.copy()
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
        
        attrs = model.root.to_obj()
        if item.is_node():
            ds.attrs = attrs
        elif item.is_var():
            ds.data_vars[item.key].attrs = attrs
        elif item.is_coord():
            ds.coords[item.key].attrs = attrs
    
    def popup_item_info(self, item: XarrayTreeItem):
        ds: xr.Dataset = item.node.dataset
        if ds is None:
            return
        if item.is_node():
            text = str(ds)
        elif item.is_var():
            text = str(ds.data_vars[item.key])
        elif item.is_coord():
            text = str(ds.coords[item.key])
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
    
    def ask_to_delete_item(self, item: XarrayTreeItem):
        answer = QMessageBox.question(self, 'Delete', f'Delete {item.path}?', QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer == QMessageBox.StandardButton.Yes:
            model: XarrayTreeModel = self.model()
            node: XarrayTreeNode = item.node
            model.remove_item(item)
            node.parent = None
            del node


def test_live():
    import sys
    import numpy as np
    app = QApplication(sys.argv)

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
    
    root_node = XarrayTreeNode(name='/', dataset=None)
    raw_node = XarrayTreeNode(name='raw data', dataset=raw_ds, parent=root_node)
    baselined_node = XarrayTreeNode(name='baselined', dataset=baselined_ds, parent=raw_node)
    scaled_node = XarrayTreeNode(name='scaled', dataset=scaled_ds, parent=baselined_node)
    # print('-----\n', root_node.to_datatree())

    root_item = XarrayTreeItem(root_node)
    model = XarrayTreeModel(root_item)
    view = XarrayTreeView()
    view.setModel(model)
    view.show()
    view.resize(QSize(600, 600))
    view.expandAll()
    view.resizeAllColumnsToContents()

    # from PySide6.QtTest import *
    # tester = QAbstractItemModelTester(model, QAbstractItemModelTester.FailureReportingMode.Fatal)

    sys.exit(app.exec())


if __name__ == '__main__':
    test_live()
