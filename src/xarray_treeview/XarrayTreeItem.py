""" Data interface with QAbstractItemModel for a tree of xarray datasets.
"""

from __future__ import annotations
import xarray as xr
from datatree import DataTree
from pyqt_ext.tree import AbstractTreeItem


class XarrayTreeItem(AbstractTreeItem):
    
    def __init__(self, node: DataTree, key: str | None = None, options: dict = {}, parent: XarrayTreeItem | None = None) -> None:
        # xarray DataTree node
        self.node: DataTree = node

        # key into xarray DataTree node, or None to refer to the node itself
        self._key = key

        AbstractTreeItem.__init__(self, name=self.name, parent=parent)

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
    
    def __repr__(self) -> str:
        # Return a single line string representation of this item.
        # See __str__ for a multi-line representation of the tree.
        node = self.node.name if self.node else None
        if node is None and self.node is not None:
            node = f'{self.node.__class__.__name__}@{id(self.node)}'
        return AbstractTreeItem.__repr__(self) + f', node={node}, key={self.key}'
    
    @AbstractTreeItem.parent.setter
    def parent(self, parent: XarrayTreeItem | None) -> None:
        if self.parent is parent:
            return
        if parent is not None:
            if not parent.is_node():
                raise ValueError('Parent must refer to a DataTree node.')
        if self.is_node():
            if parent is not None:
                if self in parent.children:
                    # should never happen
                    raise ValueError('Node already exists in parent.')
                if self.node.name in parent.node.children:
                    if parent.node.children[self.node.name] is not self.node:
                        raise ValueError(f'Node with name {self.node.name} already exists in parent.')
        elif self.is_var() or self.is_coord():
            if (parent is not None) and not parent.is_node():
                raise ValueError('Variables and coordinates must have a parent node.')
            if parent is not None:
                if parent.node is not self.node:
                    if self.name in parent.node:
                        raise ValueError(f'{self.name} already exists in parent node.')
    
        # update xarray DataTree
        if self.is_node():
            if self.node.parent is not None:
                new_parent_node: DataTree | None = parent.node if parent is not None else None
                if self.node.parent is not new_parent_node:
                    self.node.orphan()
            if parent is not None:
                if self.node.parent is not parent.node:
                    self.node.parent = parent.node
        elif self.is_var() or self.is_coord():
            old_node: DataTree = self.node
            new_node: DataTree = parent.node if parent is not None else DataTree(name=self.name)
            if new_node is not old_node:
                if self.is_var():
                    new_node.ds = new_node.to_dataset().assign({self.key: old_node[self.key]})
                elif self.is_coord():
                    new_node.ds = new_node.to_dataset().assign_coords({self.key: old_node[self.key]})
                old_node.ds = old_node.to_dataset().drop_vars([self.key])
                self.node = new_node

        # update item tree
        AbstractTreeItem.parent.fset(self, parent)
    
    @property
    def name(self) -> str:
        if self.is_node():
            return self.node.name
        if self.is_var() or self.is_coord():
            return self.key
        return f'{self.__class__.__name__}@{id(self)}'
    
    @name.setter
    def name(self, name: str) -> None:
        if self.is_node():
            if self.node.name != name:
                self.node.name = name
        if self.is_var() or self.is_coord():
            if self.key != name:
                self.key = name
    
    @property
    def key(self) -> str | None:
        return getattr(self, '_key', None)
    
    @key.setter
    def key(self, key: str | None) -> None:
        if key is not None:
            if not isinstance(key, str):
                raise ValueError('Key must be a string or None.')
            if key in self.node:
                raise ValueError(f'Key {key} already exists in node.')
            old_key = self.key
            if old_key is not None:
                self.node.ds = self.node.to_dataset().rename_vars({old_key: key})
        self._key = key
    
    def type(self) -> str:
        if self.is_node():
            return 'node'
        if self.is_var():
            return 'var'
        if self.is_coord():
            return 'coord'
    
    def is_node(self):
        return self.key is None
    
    def is_var(self):
        return (self.key is not None) and (self.key in self.node.ds.data_vars)
    
    def is_coord(self):
        return (self.key is not None) and (self.key in self.node.ds.coords)

    def get_data(self, column: int):
        if column == 0:
            return self.name
        elif column == 1:
            if self.is_node():
                sizes = self.node.ds.sizes
                return '(' + ', '.join([f'{dim}: {size}' for dim, size in sizes.items()]) + ')'
            if self.is_var():
                rep = str(self.node.ds)
                i = rep.find('Data variables:')
                i = rep.find(self.key, i)  # find var
                i = rep.find(') ', i) + 2  # skip dimensions
                i = rep.find(' ', i) + 1  # skip dtype
                i = rep.find(' ', i) + 1  # skip bytes
                j = rep.find('\n', i)
                return rep[i:j] if j > 0 else rep[i:]
            if self.is_coord():
                rep = str(self.node.ds)
                i = rep.find('Coordinates:')
                i = rep.find(self.key, i)  # find coord
                i = rep.find(') ', i) + 2  # skip dimensions
                i = rep.find(' ', i) + 1  # skip dtype
                i = rep.find(' ', i) + 1  # skip bytes
                j = rep.find('\n', i)
                return rep[i:j] if j > 0 else rep[i:]
    
    def set_data(self, column: int, value) -> bool:
        if column == 0:
            try:
                if value == self.name:
                    return False
                self.name = value
                return True
            except:
                return False
        return False


def test_tree():
    print('\nDataTree...')
    ds = xr.tutorial.load_dataset('air_temperature')
    dt = DataTree(name='root')
    child1 = DataTree(name='child1', data=ds, parent=dt)
    child2 = DataTree(name='child2', parent=dt)
    child3 = DataTree(name='child3', parent=dt)
    grandchild1 = DataTree(name='grandchild1', parent=child3)
    grandchild2 = DataTree(name='grandchild2', parent=child3)
    greatgrandchild1 = DataTree(name='greatgrandchild1', parent=grandchild1)
    greatgrandchild2 = DataTree(name='greatgrandchild2', parent=grandchild1)
    print(dt)

    print('\nXarrayTreeItem tree...')
    root = XarrayTreeItem(dt)
    print(root)


if __name__ == '__main__':
    test_tree()
