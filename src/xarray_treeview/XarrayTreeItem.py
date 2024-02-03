""" Data interface with QAbstractItemModel for a tree of xarray datasets.
"""

from __future__ import annotations
from qtpy.QtCore import *
from qtpy.QtGui import *
from qtpy.QtWidgets import *
import xarray as xr
from xarray_tree import XarrayTreeNode
from pyqt_ext import AbstractTreeItem


class XarrayTreeItem(AbstractTreeItem):
    
    def __init__(self, node: XarrayTreeNode, key = None, options: dict = {}, parent: XarrayTreeItem | None = None) -> None:
        # xarray tree node
        # This has it's own tree linkage which may differ from this item's tree linkage.
        # e.g., XarrayTreeItem may reference xarray datasets or data_vars or coords within a XarrayTreeNode
        self.node: XarrayTreeNode = node

        # key into xarray dataset, or None to refer to the dataset itself
        self.key = key

        # init tree item
        AbstractTreeItem.__init__(self, parent=parent)

        # recursively build subtree if this is a dataset and not an item (e.g., var or coord) within a node
        if key is None:
            ds: xr.Dataset = node.data if node is not None else None
            if ds is not None:
                show_vars: bool = options.get('show_vars', True)
                show_coords: bool = options.get('show_coords', True)
                if show_vars:
                    for key in ds.data_vars:
                        XarrayTreeItem(node, key, options, parent=self)
                if show_coords:
                    for key in ds.coords:
                        XarrayTreeItem(node, key, options, parent=self)
            for child in node.children.values():
                XarrayTreeItem(child, None, options, parent=self)
    
    def __repr__(self):
        if self.is_dataset():
            return self.node.name
        if self.is_var() or self.is_coord():
            return self.key
    
    def is_dataset(self):
        return self.key is None
    
    def is_var(self):
        return (self.key is not None) and (self.key in self.node.data.data_vars)
    
    def is_coord(self):
        return (self.key is not None) and (self.key in self.node.data.coords)
    
    # tree linkage ------------------------------------------------------------
    
    # def set_parent(self, parent: XarrayTreeItem | None) -> None:
    #     if not parent.is_dataset():
    #         return

    #     # update xarray tree node linkage
    #     if self.is_dataset():
    #         parent_node = parent.node if parent is not None else None
    #         if self.node.parent is not parent_node:
    #             self.node.parent = parent_node
    #     elif self.is_var():
    #         return # TODO: implement
    #     elif self.is_coord():
    #         return # TODO: implement

    #     # update tree item linkage
    #     AbstractTreeItem.set_parent(self, parent)

    #     # move to correct position in parent's list of child items
    #     # children are ordered: vars, coords, datasets
    #     if parent is not None:
    #         if self.is_dataset():
    #             # move to end of datasets
    #             desired_index = len(parent.children) - 1
    #             index = parent.children.index(self)
    #             if index != desired_index:
    #                 parent.children.insert(desired_index, parent.children.pop(index))
    #         elif self.is_var():
    #             # move to end of vars
    #             desired_index = len([item for item in parent.children if item.is_var()]) - 1
    #             index = parent.children.index(self)
    #             if index != desired_index:
    #                 parent.children.insert(desired_index, parent.children.pop(index))
    #         elif self.is_coord():
    #             # move to end of coords
    #             desired_index = len([item for item in parent.children if item.is_var() or item.is_coord()]) - 1
    #             index = parent.children.index(self)
    #             if index != desired_index:
    #                 parent.children.insert(desired_index, parent.children.pop(index))

    @property
    def path(self) -> str:
        if self.node is None:
            return self.key
        path: str = self.node.path
        if self.key is not None:
            path += '/' + self.key
        return path
    
    # interface for QAbstractItemModel ----------------------------------------
    
    def data(self, column: int):
        if column == 0:
            if self.is_dataset():
                return self.node.name
            if self.is_var() or self.is_coord():
                return self.key
        elif column == 1:
            if self.is_dataset():
                sizes = self.node.data.sizes
                return '(' + ', '.join([f'{dim}: {size}' for dim, size in sizes.items()]) + ')'
            if self.is_var():
                rep = str(self.node.data)
                i = rep.find('Data variables:')
                i = rep.find(self.key, i)  # find var
                i = rep.find(') ', i) + 2  # skip dimensions
                i = rep.find(' ', i) + 1  # skip dtype
                j = rep.find('\n', i)
                return rep[i:j] if j > 0 else rep[i:]
            if self.is_coord():
                rep = str(self.node.data)
                i = rep.find('Coordinates:')
                i = rep.find(self.key, i)  # find coord
                i = rep.find(') ', i) + 2  # skip dimensions
                i = rep.find(' ', i) + 1  # skip dtype
                j = rep.find('\n', i)
                return rep[i:j] if j > 0 else rep[i:]
    
    def set_data(self, column: int, value) -> bool:
        if column == 0:
            if self.is_dataset():
                self.node.name = value
                return True
            if self.is_var() or self.is_coord():
                # change var or coord name just for this dataset
                ds: xr.Dataset = self.node.data
                if ds is not None:
                    if value in ds.data_vars or value in ds.coords:
                        # name already exists in dataset
                        return False
                    self.node.data = ds.rename_vars({self.key: value})
                    self.key = value
                    return True
        return False


def test_tree():
    root = XarrayTreeNode(name='/')
    child1 = XarrayTreeNode(name='child1', parent=root)
    child2 = XarrayTreeNode(name='child2', parent=root)
    child3 = XarrayTreeNode(name='child3', parent=root)
    grandchild1 = XarrayTreeNode(name='grandchild1', parent=child3)
    grandchild2 = XarrayTreeNode(name='grandchild2', parent=child3)
    grandchild3 = XarrayTreeNode(name='grandchild3', parent=child3)
    greatgrandchild1 = XarrayTreeNode(name='greatgrandchild1', parent=grandchild1)
    greatgrandchild2 = XarrayTreeNode(name='greatgrandchild2', parent=grandchild1)
    greatgrandchild3 = XarrayTreeNode(name='greatgrandchild3', parent=grandchild1)
    root.dump()

    root_item = XarrayTreeItem(root)
    root_item.dump()


if __name__ == '__main__':
    test_tree()
