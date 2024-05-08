""" Tree viewer with a XarrayTreeView and Info/Attrs tabs for selected items.
"""

from __future__ import annotations
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import xarray as xr
from datatree import DataTree
from pyqt_ext.tree import KeyValueTreeItem, KeyValueTreeModel, KeyValueTreeView
from xarray_treeview import XarrayTreeItem, XarrayTreeModel, XarrayTreeView


class XarrayTreeViewer(QSplitter):

    def __init__(self, parent: QObject = None) -> None:
        QSplitter.__init__(self, Qt.Orientation.Vertical, parent)

        self._data_view = XarrayTreeView()
        self._data_view.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        model = XarrayTreeModel(None)
        model.setShowDetailsColumn(False)
        self._data_view.setModel(model)

        self._info_view = QTextEdit()
        self._info_view.setReadOnly(True)

        self._attrs_view = KeyValueTreeView()
        self._attrs_view.setModel(KeyValueTreeModel())

        self.metadata_tabs = QTabWidget()
        self.metadata_tabs.addTab(self._info_view, "Info")
        self.metadata_tabs.addTab(self._attrs_view, "Attrs")

        self.addWidget(self._data_view)
        self.addWidget(self.metadata_tabs)

        self._data_view.selectionWasChanged.connect(self._on_selection_changed)
        self._data_view.finishedEditingAttrs.connect(self._on_selection_changed)
    
    def view(self) -> XarrayTreeView:
        return self._data_view
    
    def _on_selection_changed(self) -> None:
        selected_items = self._data_view.selectedItems()
        
        if len(selected_items) != 1:
            # clear tabs
            self._info_view.clear()
            self._attrs_view.model().setRoot(KeyValueTreeItem(None, {}))
            return
        
        item: XarrayTreeItem = selected_items[0]

        if item.is_node():
            text = str(item.node.ds)
            attrs = item.node.ds.attrs
        elif item.is_var() or item.is_coord():
            text = str(item.node[item.key])
            attrs = item.node[item.key].attrs
        else:
            text = ''
            attrs = None
        
        self._info_view.setPlainText(text)
        self._attrs_view.model().setRoot(KeyValueTreeItem(None, attrs))


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
    
    viewer = XarrayTreeViewer()
    view = viewer.view()
    model = view.model()
    model.setRoot(root_item)
    viewer.show()
    viewer.resize(QSize(400, 600))
    viewer.setSizes([300, 300])
    view.expandAll()
    view.resizeAllColumnsToContents()

    app.exec()


if __name__ == '__main__':
    test_live()