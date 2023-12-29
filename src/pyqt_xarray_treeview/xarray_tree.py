""" A tree of xarray datasets.
"""

from __future__ import annotations
import numpy as np
import xarray as xr
try:
    import datatree as xt
except ImportError:
    xt = None
import scipy as sp
import lmfit


class XarrayTreeNode():

    def __init__(self, name: str, dataset: xr.Dataset | None = None, parent: XarrayTreeNode | None = None) -> None:
        self._name: str = name
        self.dataset: xr.Dataset | None = dataset
        self._parent: XarrayTreeNode | None = None  # will set to parent below
        self.children: dict[str, XarrayTreeNode] = {}
        # attach to tree
        self.parent = parent
    
    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, name: str) -> None:
        if self._name == name:
            return
        if self.parent is None:
            self._name = name
            return
        if name in self.parent.children:
            # only unique sibling names
            # name = XarrayTreeNode.unique_name(name, list(self.parent.children.keys()))
            raise Exception('sibling with this name already exists')
        self._name = name
        # update key in self.parent.children
        self.parent.children = {node.name: node for node in self.parent.children.values()}
    
    @property
    def parent(self) -> XarrayTreeNode | None:
        return self._parent
    
    @parent.setter
    def parent(self, parent: XarrayTreeNode | None) -> None:
        if self._parent is parent:
            return
        if parent is not None:
            if self.name in parent.children:
                # only unique child names
                # self.name = XarrayTreeNode.unique_name(self.name, list(parent.children.keys()))
                raise Exception('parent already has a child with this name')
        if self._parent is not None:
            # detach from self._parent
            self._parent.children.pop(self.name)
        if parent is not None:
            # attach to parent
            parent.children[self.name] = self
        self._parent = parent
    
    @property
    def path(self) -> str:
        node = self
        path = ''
        while node is not None:
            path = node.name.strip('/') + '/' + path
            node = node.parent
        return path
    
    # subtree operations
    
    def rename_vars(self, name_dict: dict[str, str]) -> None:
        """ Rename data_vars and/or coords for all nodes in this node's subtree.
        """
        # check that all name changes are valid before proceeding
        node: XarrayTreeNode = self
        while node is not None:
            ds: xr.Dataset = node.dataset
            if ds is not None:
                for old_name, new_name in name_dict.items():
                    if (old_name in ds.data_vars) or (old_name in ds.coords):
                        if (new_name in ds.data_vars) or (new_name in ds.coords):
                            raise Exception('XarrayTreeNode.rename_vars: Failed due to name overlap.')
            node = node.next_node_depth_first()
        # perform name changes
        node: XarrayTreeNode = self
        while node is not None:
            ds: xr.Dataset = node.dataset
            if ds is not None:
                node_name_dict = {}
                for old_name, new_name in name_dict.items():
                    if (old_name in ds.data_vars) or (old_name in ds.coords):
                        node_name_dict[old_name] = new_name
                if node_name_dict:
                    node.dataset = ds.rename_vars(node_name_dict)
            node = node.next_node_depth_first()
    
    # datatree compatibility

    def to_datatree(self, parent: xt.DataTree | None = None) -> xt.DataTree:
        if xt is None:
            return
        node: xt.DataTree = xt.DataTree(name=self.name, data=self.dataset, parent=parent)
        for child in self.children.values():
            child.to_datatree(node)
        return node
    
    # data inheritance
    
    def inherited_data(self, name: str) -> xr.DataArray | None:
        """ Search up the tree for a node with the given var and extract a slice over this node's coords.
        
        Any undefined coords will also be inherited.
        """
        node = self
        while node is not None:
            ds: xr.Dataset = node.dataset
            if (ds is not None) and (name in ds.data_vars):
                var: xr.DataArray = ds.data_vars[name]#.copy(deep=False)
                for dim in ds.dims:
                    if dim not in var.coords:
                        if dim in ds.coords:
                            var.coords[dim] = ds.coords[dim]
                        else:
                            var.coords[dim] = node.inherited_coord(dim)
                if node is self:
                    return var
                else:
                    return var.sel(self.inherited_coords())
            node = node.parent

    def leaf_data(self, name: str, root: XarrayTreeNode = None) -> xr.DataArray | None:
        """ Return copy of var from root to self, with data from descendents overwritting their coord parts of data from ancestors.
        
        Start with a copy of values for the named data_var in root.
        Overwrite any values with those of the named data_var in deeper nodes along the tree path from root to this node.
        """
        if root is None:
            root = self
            while root.parent is not None:
                root = root.parent
        if root is self:
            return self.inherited_data(name)
        node_path: list[XarrayTreeNode] = [self]
        while node_path[0].parent is not None:
            node_path.insert(0, node_path[0].parent)
            if node_path[0] is root:
                break
        while node_path:
            ds: xr.Dataset = node_path[0].dataset
            if (ds is not None) and (name in ds.data_vars):
                break
            else:
                node_path.pop(0)
        if not node_path:
            return None
        node: XarrayTreeNode = node_path.pop(0)
        ds: xr.Dataset = node.dataset
        var: xr.DataArray = ds.data_vars[name].copy(deep=True)
        for dim in ds.dims:
            if dim not in var.coords:
                var.coords[dim] = node.inherited_coord(dim)
        if node_path:
            for node in node_path:
                ds: xr.Dataset = node.dataset
                if (ds is not None) and (name in ds.data_vars):
                    coords = {}
                    for dim in var.dims:
                        if dim in ds.coords:
                            coords[dim] = ds.coords[dim]
                        else:
                            coords[dim] = node.inherited_coord(dim)
                    var.loc[coords] = ds.data_vars[name].values
        return var

    def inherited_coord(self, name: str) -> xr.DataArray:
        """ Search up the tree for a node with the given coord.
        
        If not found, return index array for this node's dimension with same name.
        """
        node: XarrayTreeNode = self
        while node is not None:
            ds: xr.Dataset = node.dataset
            if (ds is not None) and (name in ds.coords):
                    coord: xr.DataArray = ds.coords[name]
                    for dim in coord.dims:
                        if coord.sizes[dim] != self.dataset.sizes[dim]:
                            return xr.DataArray(dims=(name,), data=np.arange(self.dataset.dims[name]))
                    return coord
            node = node.parent
        return xr.DataArray(dims=(name,), data=np.arange(self.dataset.dims[name]))
    
    def inherited_coords(self) -> dict[str, xr.DataArray]:
        """ Return dict of coords (inherited if needed) for all dims in this node.
        """
        coords: dict = {}
        ds: xr.Dataset = self.dataset
        for dim in ds.dims:
            if dim in ds.coords:
                coords[dim] = ds.coords[dim]
            else:
                coords[dim] = self.inherited_coord(dim)
        return coords
    
    # data operations

    def reduce(
        self,
        names: list[str],
        op: np.ufunc,
        dim: str = None,
        coords: dict = None,
        result_name: str = None,
        append_mode: str = 'merge or replace'
        ) -> XarrayTreeNode | None:
        """ Apply reduction to dataset and append results in child node.
        """
        ds: xr.Dataset = self.dataset
        if ds is None:
            return None
        
        along_dim = dim
        
        if coords is not None:
            for dim in ds.dims:
                if dim not in coords:
                    coords[dim] = self.inherited_coord(dim)
        
        if result_name is None:
            result_name = op.__name__
            if along_dim is not None:
                result_name = along_dim + ' ' + result_name
    
        data = xr.Dataset()
        for name in names:
            var = self.inherited_data(name)
            if var is not None:
                if coords is not None:
                    var = var.sel(coords)
                data[name] = var
        
        result = data.reduce(op, dim=along_dim)

        # store result as child node
        child_names = [name for name in self.children.keys()]
        if result_name not in child_names:
            return XarrayTreeNode(name=result_name, dataset=result, parent=self)
        # child node with result name already exists
        if append_mode == 'do not merge or replace':
            return
        if append_mode == 'replace':
            # remove child to replace
            self.children.pop(result_name)
            # replace with results
            return XarrayTreeNode(name=result_name, dataset=result, parent=self)
        if append_mode == 'merge' or append_mode == 'merge or replace':
            try:
                child: XarrayTreeNode = self.children[result_name]
                # merge result with child dataset (use result for any overlap)
                child.dataset: xr.Dataset = result.combine_first(child.dataset)
                return child
            except:
                if append_mode == 'merge or replace':
                    # remove child to replace
                    self.children.pop(result_name)
                    # replace with results
                    return XarrayTreeNode(name=result_name, dataset=result, parent=self)
    
    def curve_fit(
        self,
        names: list[str],
        fit_expr: str,
        xdim: str,
        options: dict = None,
        xdata_to_optimize = None,
        coords: dict = None,
        result_name: str = None,
        append_mode: str = 'merge or replace'
        ) -> XarrayTreeNode | None:
        """ Apply curve fit to dataset and append results in child node.
        """
        ds: xr.Dataset = self.dataset
        if ds is None:
            return None
        
        if options is None:
            options = {}
        
        if coords is not None:
            for dim in ds.dims:
                if dim not in coords:
                    coords[dim] = self.inherited_coord(dim)
        
        if result_name is None:
            result_name = fit_expr
        
        optimization_coords = coords
        if xdata_to_optimize is not None:
            if optimization_coords is None:
                optimization_coords = self.inherited_coords()
            else:
                optimization_coords = coords.copy()
            optimization_coords[xdim] = xdata_to_optimize
        
        permutation_coords = coords.copy()
        if permutation_coords is None:
            permutation_coords = self.inherited_coords()
        del permutation_coords[xdim]
        permutation_coords = XarrayTreeNode.permutations(permutation_coords)
    
        data = xr.Dataset()
        fit = xr.Dataset()
        for name in names:
            var = self.inherited_data(name)
            if var is not None:
                if optimization_coords is None:
                    data[name] = var
                else:
                    data[name] = var.sel(optimization_coords)
                # this is just allocation, we'll overwrite with actual fit data
                if coords is None:
                    fit[name] = var
                else:
                    fit[name] = var.sel(coords)
        
        # store fit info as attrs
        fit_attrs: dict = {
            'expression': fit_expr
        }
        if options:
            fit_attrs['options'] = options
        
        for name in data.data_vars:
            for coord in permutation_coords:
                # data to optimize fit
                coord[xdim] = optimization_coords[xdim]
                xdata = coord[xdim]
                if isinstance(xdata, xr.DataArray):
                    xdata = xdata.values
                ydata = data[name].sel(coord).values
                # fit result coords
                coord[xdim] = coords[xdim]
                xfit = coord[xdim]
                if isinstance(xfit, xr.DataArray):
                    xfit = xfit.values
                # do fit
                if fit_expr.lower() == 'mean':
                    yfit = np.mean(ydata)
                elif fit_expr.lower() == 'median':
                    yfit = np.median(ydata)
                elif fit_expr.lower() == 'min':
                    yfit = np.min(ydata)
                elif fit_expr.lower() == 'max':
                    yfit = np.max(ydata)
                elif fit_expr.lower() == 'absmax':
                    yfit = np.max(np.abs(ydata))
                elif fit_expr.lower() == 'polynomial':
                    degree = options['degree']
                    coef = np.polyfit(xdata, ydata, degree)
                    yfit = np.polyval(coef, xfit)
                elif fit_expr.lower() == 'spline':
                    n_segments = options['segments']
                    segment_length = max(1, int(len(ydata) / n_segments))
                    knots = xdata[segment_length:-segment_length:segment_length]
                    if len(knots) < 2:
                        knots = xdata[[1, -2]]
                    knots, coef, degree = sp.interpolate.splrep(xdata, ydata, t=knots)
                    yfit = sp.interpolate.splev(xfit, (knots, coef, degree), der=0)
                else:
                    equation = fit_expr
                    fit_model = lmfit.models.ExpressionModel(equation, independent_vars=['x'])
                    for param_name in fit_model.param_names:
                        hint = {}
                        try:
                            hint['value'] = options['params'][param_name]['value']
                        except:
                            pass
                        try:
                            lower_bound, upper_bound = options['params'][param_name]['bounds']
                            hint['min'] = lower_bound
                            hint['max'] = upper_bound
                            if 'value' in hint:
                                if hint['value'] < lower_bound:
                                    hint['value'] = lower_bound
                                elif hint['value'] > upper_bound:
                                    hint['value'] = upper_bound
                        except:
                            pass
                        fit_model.set_param_hint(param_name, **hint)
                    params = fit_model.make_params()
                    for param_name, param in params.items():
                        try:
                            param.vary = options['params'][param_name]['vary']
                        except:
                            pass
                    result = fit_model.fit(ydata, params, x=xdata)
                    # print(result.fit_report())
                    yfit = fit_model.eval(result.params, x=xfit)
                    fit_attrs['optimized'] = result.params
                # apply fit results
                if yfit is None:
                    fit[name].loc[coord] = np.nan
                else:
                    fit[name].loc[coord] = yfit
        fit.attrs['fit'] = fit_attrs

        # store fit as child node
        child_names = [name for name in self.children.keys()]
        if result_name not in child_names:
            return XarrayTreeNode(name=result_name, dataset=fit, parent=self)
        # child node with result name already exists
        if append_mode == 'do not merge or replace':
            return
        if append_mode == 'replace':
            # remove child to replace
            self.children.pop(result_name)
            # replace with results
            return XarrayTreeNode(name=result_name, dataset=fit, parent=self)
        if append_mode == 'merge' or append_mode == 'merge or replace':
            try:
                child: XarrayTreeNode = self.children[result_name]
                # merge fit with child dataset (use fit for any overlap)
                child.dataset: xr.Dataset = fit.combine_first(child.dataset)
                return child
            except:
                if append_mode == 'merge or replace':
                    # remove child to replace
                    self.children.pop(result_name)
                    # replace with results
                    return XarrayTreeNode(name=result_name, dataset=fit, parent=self)
    
    # tree traversal
    
    def root(self) -> XarrayTreeNode:
        node: XarrayTreeNode = self
        while node.parent is not None:
            node = node.parent
        return node
    
    def first_child(self) -> XarrayTreeNode | None:
        if self.children:
            return list(self.children.values())[0]

    def last_child(self) -> XarrayTreeNode | None:
        if self.children:
            return list(self.children.values())[-1]

    def first_sibling(self) -> XarrayTreeNode:
        if self.parent is not None:
            return self.parent.first_child()
        return self

    def last_sibling(self) -> XarrayTreeNode:
        if self.parent is not None:
            return self.parent.last_child()
        return self

    def siblings(self) -> list[XarrayTreeNode]:
        if self.parent is not None:
            return list(self.parent.children.values())
        return [self]
    
    def next_sibling(self) -> XarrayTreeNode | None:
        siblings: list[XarrayTreeNode] = self.siblings()
        if siblings:
            i: int = siblings.index(self)
            if i+1 < len(siblings):
                return siblings[i+1]

    def prev_sibling(self) -> XarrayTreeNode | None:
        siblings: list[XarrayTreeNode] = self.siblings()
        if siblings:
            i: int = siblings.index(self)
            if i-1 >= 0:
                return siblings[i-1]

    def last_node_depth_first(self) -> XarrayTreeNode:
        node: XarrayTreeNode = self
        while node.children:
            node = node.last_child()
        return node

    def next_node_depth_first(self) -> XarrayTreeNode | None:
        if self.children:
            return self.first_child()
        next_sibling: XarrayTreeNode = self.next_sibling()
        if next_sibling is not None:
            return next_sibling
        node: XarrayTreeNode = self.parent
        while node is not None:
            next_sibling: XarrayTreeNode = node.next_sibling()
            if next_sibling is not None:
                return next_sibling
            node = node.parent

    def prev_node_depth_first(self) -> XarrayTreeNode | None:
        prev_sibling: XarrayTreeNode = self.prev_sibling()
        if prev_sibling is not None:
            return prev_sibling.last_node_depth_first()
        if self.parent is not None:
            return self.parent
    
    def sibling_index(self) -> int:
        if self.parent is None:
            return 0
        return list(self.parent.children.values()).index(self)
    
    def depth(self) -> int:
        depth: int = 0
        node: XarrayTreeNode = self
        while node.parent is not None:
            depth += 1
            node = node.parent
        return depth
    
    def subtree_max_depth(self) -> int:
        root_depth: int = self.depth()
        max_depth: int = 0
        node: XarrayTreeNode = self.next_node_depth_first()
        while node is not None:
            depth: int = node.depth()
            if depth - root_depth > max_depth:
                max_depth = depth - root_depth
            node = node.next_node_depth_first()
        return max_depth
    
    def dump(self, indent: int = 0):
        print(' ' * indent + self.name)
        for child in self.children.values():
            child.dump(indent + 4)
    
    # static methods

    @staticmethod
    def permutations(coords: dict) -> list[dict]:
        """ return list of all permutations of coords along each dimension

        Example:
            coords = {'subject': [0, 1], 'trial': [0, 1, 2]}
            permutations(coords) = [
                {'subject': 0, 'trial': 0},
                {'subject': 0, 'trial': 1},
                {'subject': 0, 'trial': 2},
                {'subject': 1, 'trial': 0},
                {'subject': 1, 'trial': 1},
                {'subject': 1, 'trial': 2},
            ]
        """
        for dim in coords:
            # ensure coords[dim] is iterable
            try:
                iter(coords[dim])
            except:
                coords[dim] = [coords[dim]]
        permutations: list[dict] = []
        dims = list(coords)
        index = {dim: 0 for dim in dims}
        while index is not None:
            try:
                # coord for index
                coord = {dim: coords[dim][i] for dim, i in index.items()}
                # store coord
                permutations.append(coord)
            except:
                pass
            # next index
            for dim in reversed(dims):
                if index[dim] + 1 < len(coords[dim]):
                    index[dim] += 1
                    break
                elif dim == dims[0]:
                    index = None
                    break
                else:
                    index[dim] = 0
        return permutations
    
    @staticmethod
    def unique_name(name: str, names: list[str]) -> str:
        if name not in names:
            return name
        i: int = 1
        uname = name + f'_{i}'
        while uname in names:
            i += 1
            uname = name + f'_{i}'
        return uname


def test():
    root_ds = xr.Dataset(
        data_vars={
            'current': (['series', 'sweep', 'time'], np.random.rand(3, 10, 100) * 1e-9, {'units': 'A'}),
            'voltage': (['series', 'sweep', 'time'], np.random.rand(3, 10, 100) * 10000, {'units': 'V'}),
        },
        coords={
            'time': ('time', np.arange(100) * 0.01, {'units': 's'}),
        },
    )
    # print('-----\n root_ds', root_ds)

    baselined_ds = root_ds.drop_vars(['voltage', 'time']).copy(deep=True)
    # print('-----\n baselined_ds', baselined_ds)

    scaled_ds = baselined_ds.isel(series=[1], sweep=[5,8]).copy(deep=True)
    scaled_ds.coords['series'] = [1]
    scaled_ds.coords['sweep'] = [5,8]
    # print('-----\n scaled_ds', scaled_ds)
    
    root_node = XarrayTreeNode(name='raw data', dataset=root_ds)
    baselined_node = XarrayTreeNode(name='baselined', dataset=baselined_ds, parent=root_node)
    scaled_node = XarrayTreeNode(name='scaled', dataset=scaled_ds, parent=baselined_node)
    # print('-----\n root_node', root_node)

    # print('-----\n')
    # root_node.dump()

    root_voltage = root_node.inherited_data('voltage')
    # print('-----\n root_voltage', root_voltage)
    assert(np.allclose(root_voltage.values, root_ds['voltage'].values))

    baselined_voltage = baselined_node.inherited_data('voltage')
    # print('-----\n baselined_voltage', baselined_voltage)
    assert(np.allclose(baselined_voltage.values, root_voltage.values))

    scaled_voltage = scaled_node.inherited_data('voltage')
    # print('-----\n scaled_voltage', scaled_voltage)
    assert(np.allclose(scaled_voltage.values, root_voltage.sel(scaled_voltage.coords).values))

    scaled_leaf_current = scaled_node.leaf_data('current')
    scaled_current = scaled_node.inherited_data('current')
    root_current = root_ds['current'].copy(deep=True)
    leaf_current = root_current
    leaf_current.loc[scaled_current.coords] = scaled_current
    assert(np.allclose(scaled_leaf_current.values, leaf_current.values))

    result_node = scaled_node.reduce(['current'], np.max, dim='sweep', result_name='sweep max')
    # print('----------\n sweep max', result_node)
    result_current = result_node.dataset['current']
    scaled_current = scaled_node.inherited_data('current')
    sweep_max_scaled_current = scaled_current.reduce(np.max, dim='sweep')
    assert(np.allclose(result_current.values, sweep_max_scaled_current.values))

    result_node = baselined_node.reduce(['current'], np.mean, dim='series', result_name='series mean')
    # print('----------\n series mean', result_node)
    result_current = result_node.dataset['current']
    baselined_current = baselined_node.inherited_data('current')
    series_mean_baselined_current = baselined_current.reduce(np.mean, dim='series')
    assert(np.allclose(result_current.values, series_mean_baselined_current.values))

    result_node = root_node.reduce(['current'], np.min, dim='time', result_name='time min')
    # print('----------\n time min', result_node)
    result_current = result_node.dataset['current']
    root_current = root_node.inherited_data('current')
    time_min_root_current = root_current.reduce(np.min, dim='time')
    assert(np.allclose(result_current.values, time_min_root_current.values))

    coords = {'series': [1,2]}
    result_node = root_node.reduce(['voltage'], np.median, dim='sweep', result_name='sweep median', coords=coords)
    # print('----------\n sweep median', result_node.data)
    result_voltage = result_node.dataset['voltage']
    root_voltage = root_node.inherited_data('voltage').sel(result_node.inherited_coords())
    sweep_median_root_voltage = root_voltage.reduce(np.median, dim='sweep')
    assert(np.allclose(result_voltage.values, sweep_median_root_voltage.values))

    coords = {'series': [1,2]}
    result_node = root_node.reduce(['voltage'], np.median, dim='sweep', result_name='sweep median', coords=coords)
    # print('----------\n sweep median', result_node.data)
    result_voltage = result_node.dataset['voltage']
    root_voltage = root_node.inherited_data('voltage').sel(result_node.inherited_coords())
    sweep_median_root_voltage = root_voltage.reduce(np.median, dim='sweep')
    assert(np.allclose(result_voltage.values, sweep_median_root_voltage.values))

    coords = {'series': [0,2]}
    result_node = root_node.reduce(['voltage'], np.median, dim='sweep', result_name='sweep median', coords=coords)
    # print('----------\n sweep median', result_node.data)
    result_voltage = result_node.dataset['voltage']
    root_voltage = root_node.inherited_data('voltage').sel(result_node.inherited_coords())
    sweep_median_root_voltage = root_voltage.reduce(np.median, dim='sweep')
    assert(np.allclose(result_voltage.values, sweep_median_root_voltage.values))

    result_node = baselined_node.reduce(['voltage'], np.median, result_name='median')
    # print('----------\n median', result_node.data)
    result_voltage = result_node.dataset['voltage']
    root_voltage = root_node.inherited_data('voltage').sel(result_node.inherited_coords())
    median_root_voltage = root_voltage.reduce(np.median)
    assert(np.allclose(result_voltage.values, median_root_voltage.values))
    
    # print('-----\n', root_node.to_datatree())

    print('-----\n')
    root_node.dump()

    root_node.children['baselined'].children['scaled'].parent = None
    print('-----\n')
    root_node.dump()
   
    print('-----\n ALL TESTS: OK')


if __name__ == '__main__':
    test()
