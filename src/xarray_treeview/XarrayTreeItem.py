""" Data interface with QAbstractItemModel for a tree of xarray datasets.
"""

from __future__ import annotations
import xarray as xr
from datatree import DataTree
from pyqt_ext import AbstractTreeItem


class XarrayTreeItem(AbstractTreeItem):
    
    def __init__(self, node: DataTree, key = None, options: dict = {}, parent: XarrayTreeItem | None = None) -> None:
        # xarray DataTree node
        self.node: DataTree = node

        # key into xarray DataTree node, or None to refer to the node itself
        self.key = key

        AbstractTreeItem.__init__(self, parent=parent)

        # recursively build subtree if this is a dataset and not a data_var or coord within a dataset
        if key is None:
            show_vars: bool = options.get('show_vars', True)
            show_coords: bool = options.get('show_coords', True)
            if show_vars:
                for key in node.ds.data_vars:
                    XarrayTreeItem(node, key, options, parent=self)
            if show_coords:
                for key in node.ds.coords:
                    XarrayTreeItem(node, key, options, parent=self)
            for child in node.children.values():
                XarrayTreeItem(child, None, options, parent=self)
    
    def __repr__(self):
        if self.is_dataset():
            return self.node.name
        if self.is_var() or self.is_coord():
            return self.key
    
    @property
    def path(self) -> str:
        path: str = self.node.path
        if self.key is not None:
            path += '/' + self.key
        return path
    
    def is_dataset(self):
        return self.key is None
    
    def is_var(self):
        return (self.key is not None) and (self.key in self.node.ds.data_vars)
    
    def is_coord(self):
        return (self.key is not None) and (self.key in self.node.ds.coords)
    
    @AbstractTreeItem.parent.setter
    def parent(self, parent: XarrayTreeItem | None) -> None:
        old_parent = self.parent
        if self.parent is parent:
            return
        if (parent is not None) and (not parent.is_dataset()):
            raise ValueError('Parent must be a Dataset.')
        if self.parent is not None:
            # detach from old parent
            if self in self.parent.children:
                # remove node from tree
                self.node.parent = None
                # remove item from parent's children
                self.parent.children.remove(self)
            self._parent = None
        if parent is not None:
            # attach to new parent
            if self not in parent.children:
                # insert node into tree
                try:
                    if self.is_dataset():
                        self.node.parent = parent.node
                    elif self.is_var():
                        ds: xr.Dataset = xr.Dataset(
                            data_vars={
                                self.key: self.node.to_dataset()[self.key]
                            }
                        )
                        parent.node.ds = ds.combine_first(parent.node.to_dataset())
                    elif self.is_coord():
                        ds: xr.Dataset = xr.Dataset(
                            coords={
                                self.key: self.node.to_dataset()[self.key]
                            }
                        )
                        parent.node.ds = ds.combine_first(parent.node.to_dataset())
                    # insert into parent's children
                    parent.children.append(self)
                except:
                    self.parent = old_parent
                    return
            self._parent = parent

    def data(self, column: int):
        if column == 0:
            if self.is_dataset():
                return self.node.name
            if self.is_var() or self.is_coord():
                return self.key
        elif column == 1:
            if self.is_dataset():
                sizes = self.node.ds.sizes
                return '(' + ', '.join([f'{dim}: {size}' for dim, size in sizes.items()]) + ')'
            if self.is_var():
                rep = str(self.node.ds)
                i = rep.find('Data variables:')
                i = rep.find(self.key, i)  # find var
                i = rep.find(') ', i) + 2  # skip dimensions
                i = rep.find(' ', i) + 1  # skip dtype
                j = rep.find('\n', i)
                return rep[i:j] if j > 0 else rep[i:]
            if self.is_coord():
                rep = str(self.node.ds)
                i = rep.find('Coordinates:')
                i = rep.find(self.key, i)  # find coord
                i = rep.find(') ', i) + 2  # skip dimensions
                i = rep.find(' ', i) + 1  # skip dtype
                j = rep.find('\n', i)
                return rep[i:j] if j > 0 else rep[i:]
    
    def set_data(self, column: int, value) -> bool:
        if column == 0:
            if self.is_dataset():
                if (self.node.parent is not None) and (value in self.node.parent.children):
                    # name already exists in siblings
                    return False
                self.node.name = value  # TODO: This break tree linkage because the old key in self.node.parent.children is not updated.
                return True
            if self.is_var() or self.is_coord():
                if value in self.node.ds:
                    # name already exists in dataset
                    return False
                self.node.ds = self.node.to_dataset().rename_vars({self.key: value})
                self.key = value
                return True
        return False


def test_tree():
    ds = xr.tutorial.load_dataset('air_temperature')

    root = DataTree(name='root')
    child1 = DataTree(name='child1', data=ds, parent=root)
    child2 = DataTree(name='child2', parent=root)
    child3 = DataTree(name='child3', parent=root)
    grandchild1 = DataTree(name='grandchild1', parent=child3)
    grandchild2 = DataTree(name='grandchild2', parent=child3)
    greatgrandchild1 = DataTree(name='greatgrandchild1', parent=grandchild1)
    greatgrandchild2 = DataTree(name='greatgrandchild2', parent=grandchild1)
    print(root)

    root_item = XarrayTreeItem(root)
    print(root_item)


if __name__ == '__main__':
    test_tree()
