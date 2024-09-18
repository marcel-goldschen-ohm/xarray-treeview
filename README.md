# xarray-treeview
PyQt/PySide tree model/view interface for an Xarray DataTree.

![GitHub Tag](https://img.shields.io/github/v/tag/marcel-goldschen-ohm/xarray-treeview?cacheSeconds=1)
![build-test](https://github.com/marcel-goldschen-ohm/xarray-treeview/actions/workflows/build-test.yml/badge.svg)
![GitHub Release](https://img.shields.io/github/v/release/marcel-goldschen-ohm/xarray-treeview?include_prereleases&cacheSeconds=1)
![publish](https://github.com/marcel-goldschen-ohm/xarray-treeview/actions/workflows/publish.yml/badge.svg)

- [Install](#install)
- [Quick Start](#quick-start)
- [Documentation](#documentation)

## Install
Requires a PyQt package. Should work with PySide6, PyQt6, or PyQt5.
```shell
pip install PySide6
```
Install latest release version:
```shell
pip install xarray-treeview
```
Or install latest development version:
```shell
pip install xarray-treeview@git+https://github.com/marcel-goldschen-ohm/xarray-treeview
```

## Quick Start
```python
from qtpy.QtWidgets import QApplication
from xarray_treeview import *

app = QApplication()

# Xarray DataTree
dt: DataTree = ...

# XarrayTreeModel: without drag-n-drop
# XarrayDndTreeModel: with drag-n-drop (move within tree only)
model = XarrayDndTreeModel()
model.setDataTree(dt)

# XarrayTreeViewer includes XarrayTreeView plus info and attrs views
# but you can use XarrayTreeView standalone too.
viewer = XarrayTreeViewer()
view: XarrayTreeView = viewer.view()
view.setModel(model)

viewer.show()
app.exec()
```

## Documentation
:construction:
