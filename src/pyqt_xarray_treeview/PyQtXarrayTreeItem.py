""" Data interface with QAbstractItemModel for a tree of xarray datasets.
"""

from __future__ import annotations
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import xarray as xr
from pyqt_ext import AbstractTreeItem
from pyqt_xarray_treeview import XarrayTreeNode


class XarrayTreeItem(AbstractTreeItem):
    
    def __init__(self, node: XarrayTreeNode, key = None, options: dict = {}, parent: XarrayTreeItem | None = None) -> None:
        AbstractTreeItem.__init__(self, parent=parent)
        self.node: XarrayTreeNode = node
        self.key = key  # key for data within node, e.g., node.dataset[key]

        # recursively build subtree if this is a node and not an item (e.g., var or coord) within a node
        if key is None:
            ds: xr.Dataset = node.dataset if node is not None else None
            if ds is not None:
                show_vars: bool = not options.get('hide_vars', False) and options.get('show_vars', True)
                show_coords: bool = not options.get('hide_coords', False) and options.get('show_coords', True)
                if show_vars:
                    items: list[XarrayTreeItem] = [XarrayTreeItem(node, key, options, parent=self) for key in ds.data_vars]
                    self.append_children(items)
                if show_coords:
                    items: list[XarrayTreeItem] = [XarrayTreeItem(node, key, options, parent=self) for key in ds.coords]
                    self.append_children(items)
            for child in node.children.values():
                self.children.append(XarrayTreeItem(child, None, options, parent=self))
    
    def __repr__(self):
        if self.is_node():
            return self.node.name
        if self.is_var() or self.is_coord():
            return self.key
    
    @property
    def path(self) -> str:
        if self.node is None:
            return
        path: str = self.node.path
        if self.key is not None:
            path += self.key
        return path
    
    def is_node(self):
        return self.key is None
    
    def is_var(self):
        return (self.key is not None) and (self.key in self.node.dataset.data_vars)
    
    def is_coord(self):
        return (self.key is not None) and (self.key in self.node.dataset.coords)
    
    def data(self, column: int):
        if column == 0:
            if self.is_node():
                return self.node.name
            if self.is_var() or self.is_coord():
                return self.key
        elif column == 1:
            if self.is_node():
                sizes = self.node.dataset.sizes
                return '(' + ', '.join([f'{dim}: {size}' for dim, size in sizes.items()]) + ')'
            if self.is_var():
                rep = str(self.node.dataset)
                i = rep.find('Data variables:')
                i = rep.find(self.key, i)  # find var
                i = rep.find(') ', i) + 2  # skip dimensions
                i = rep.find(' ', i) + 1  # skip dtype
                j = rep.find('\n', i)
                return rep[i:j] if j > 0 else rep[i:]
            if self.is_coord():
                rep = str(self.node.dataset)
                i = rep.find('Coordinates:')
                i = rep.find(self.key, i)  # find coord
                i = rep.find(') ', i) + 2  # skip dimensions
                i = rep.find(' ', i) + 1  # skip dtype
                j = rep.find('\n', i)
                return rep[i:j] if j > 0 else rep[i:]
    
    def set_data(self, column: int, value) -> bool:
        if column == 0:
            if self.is_node():
                self.node.name = value
                return True
            if self.is_var() or self.is_coord():
                # change var or coord name just for this dataset
                ds: xr.Dataset = self.node.dataset
                if ds is not None:
                    if value in ds.data_vars or value in ds.coords:
                        # name already exists in dataset
                        return False
                    self.node.dataset = ds.rename_vars({self.key: value})
                    self.key = value
                    return True
        return False
