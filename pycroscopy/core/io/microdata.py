# -*- coding: utf-8 -*-
"""
Created on Wed Dec 16 10:42:03 2015

@author: Suhas Somnath, Numan Laanait

The MicroData classes

"""

from __future__ import division, print_function, absolute_import, unicode_literals
import socket
from warnings import warn
import numpy as np
import sys

from .io_utils import get_time_stamp

if sys.version_info.major == 3:
    unicode = str


class MicroData(object):
    """
    Generic class that is extended by the MicroDataGroup and MicroDataset objects
    """

    def __init__(self, name, parent, attrs=None):
        """
        Parameters
        ----------
        name : String
            Name of the data group / dataset object
        parent : String
            HDF5 path to the parent of this object. Typically used when
            appending to an existing HDF5 file
        attrs : dict (Optional). Default = None
            Attributes of the object
        """
        if attrs is not None:
            if not isinstance(attrs, dict):
                raise TypeError('attrs should be of type: dict')
            self.attrs = attrs
        else:
            self.attrs = dict()
        self.name = name
        self.parent = parent
        self.indexed = False


class MicroDataGroup(MicroData):
    """
    Holds data that will be converted to a h5.Group by io.HDFwriter
    Note that it can also hold information (e.g. attributes) of an h5.File.
    This is consistent with class hierarchy of HDF5, i.e. h5.File extends h5.Group.
    """

    def __init__(self, name, parent='/', attrs=None, children=None):
        """
        Parameters
        ----------
        name : String
            Name of the data group
        parent : (Optional) String
            HDF5 path to the parent of this object. Typically used when
            appending to an existing HDF5 file
            Default value assumes that this group sits at the root of the file
        attrs : dict (Optional). Default = None
            Attributes to be attached to the h5py.Group object
         children : MicroData or list of MicroData objects. (Optional)
            Children can be a mixture of groups and datasets
        """
        super(MicroDataGroup, self).__init__(name, parent, attrs=attrs)
        self.children = list()
        self.attrs['machine_id'] = socket.getfqdn()
        self.attrs['timestamp'] = get_time_stamp()

        self.indexed = False

        if name != '':
            self.indexed = self.name[-1] == '_'

        if children is not None:
            self.add_children(children)

    def add_children(self, children):
        """
        Adds Children to the class to make a tree structure.

        Parameters
        ----------
        children : MicroData or list of MicroData objects
            Children can be a mixture of groups and datasets

        Returns
        -------
        None
        """
        if not isinstance(children, (tuple, list)):
            children = [children]
        for child in children:
            if isinstance(child, MicroData):
                child.parent = self.parent + self.name
                self.children.append(child)
            else:
                warn('Children must be of type MicroData. child ignored')

    def __str__(self):
        self.show_tree()

    def show_tree(self):
        """
        Return the tree structure given by MicroDataGroup.
        """

        def __tree(child, parent):
            print(parent + '/' + child.name)
            if isinstance(child, MicroDataGroup):
                for ch in child.children:
                    __tree(ch, parent + '/' + child.name)

        # print(self.parent+self.name)
        for curr_child in self.children:
            __tree(curr_child, self.parent + self.name)


class MicroDataset(MicroData):
    """
    Holds data (i.e. numpy.ndarray) as well as instructions on writing, attributes, etc...
    This gets converted to a h5py.Dataset by io.HDFwriter

    Region references need to be specified using the 'labels' attribute. See example below    
    """

    def __init__(self, name, data, dtype=None, compression=None, chunking=None, parent=None, resizable=False,
                 maxshape=None, attrs=None):
        """
        Parameters
        ----------
        name : String
            Name of the dataset
        data : Object
            See supported objects in h5py
        dtype : datatype, 
            typically a datatype of a numpy array =None
        compression : (Optional) String
            See h5py compression. Leave as 'gzip' as a default mode of compression
        chunking : (Optional) tuple of ints
            Chunking in each dimension of the dataset. If not provided, 
            default chunking is used by h5py when writing this dataset
        parent : (Optional) String
                HDF5 path to the parent of this object. This value is overwritten
                when this dataset is made the child of a datagroup. Default = under root
        resizable : Boolean (Optional. default = False)
            Whether or not this dataset is expected to be resizeable.
            Note - if the dataset is resizable the specified maxsize will be ignored. 
        maxshape : (Optional) tuple of ints
            Maximum size in each axis this dataset is expected to be
            if this parameter is provided, io will ONLY allocate space. 
            Make sure to specify the dtype appropriately. The provided data will be ignored
        attrs : dict (Optional). Default = None
            Attributes to be attached to the h5py.Dataset object
            
        Examples
        --------   
        1. Small auxiliary datasets :
            Make sure to specify the name and data. All other parameters are optional

        >>> ds_ex_efm = MicroDataset('Excitation_Waveform', np.arange(10))
            
        2. Initializing large primary datasets of known sizes :
            Ensure that the name, maxshape are specified and that maxshape does not have any elements that are None.
            All other arguments are optional.
        
        >>> ds_raw_data = MicroDataset('Raw_Data', None, maxshape=(1024,16384), dtype=np.float16,
        >>>                            chunking=(1,16384), compression='gzip')
                    
        3. Initializing large datasets whose size is unknown in one or more dimensions:
            Ensure to specify the name, set resizable to True, and some initial data (can be zeros but of appropriate
            shape) to start with.
            It is recommended that you allow the dataset to grow only in the necessary dimensions since HDFwriter will
            assume that the dataset will grow in all dimensions by default. In the example below, the dataset will only
            grow in the first dimension while the size in the second dimension is fixed because of maxshape.
        
        >>> ds_raw_data = MicroDataset('Raw_Data', np.zeros(shape=(1,16384), dtype=np.complex64), resizable=True,
        >>>                            maxshape=(None, 16384), chunking=(1,16384), compression='gzip')

        Once HDFwriter is used to write the dataset, you will need to use the resize function in h5py as:

        >>> h5_dataset.resize(h5_dataset.shape[0] + 1, axis = 0)

        This will increment the size of the dataset in the first axis from it's current value (of 1) to 2.

        Note that the HDF5 file containing datasets that have been expanded this way are bound to be noticeably larger
        in size compared to files with datasets that are not allowed to expand. Therefore, use this only when absolutely
        necessary only.

        4. Datasets with region references :

        >>> ds_spec_inds = MicroDataset('Spectroscopic_Indices', np.random.random(1, 10))
            ds_spec_inds.attrs['labels'] = {'Time Index':(slice(0,1), slice(None))}
        """
        if parent is None:
            parent = '/'  # by default assume it is under root

        super(MicroDataset, self).__init__(name, parent, attrs=attrs)

        assert isinstance(name, (str, unicode)), 'Name should be a string'

        def _make_iterable(param):
            if param is not None:
                if type(param) not in [list, tuple]:  # another (inelegant) way of asking if this object is iterable
                    param = tuple([param])
            return param

        def _valid_shapes(param, none_ok=False):
            if param is None:
                return True
            tests = []
            for item in param:
                if item is None:
                    tests.append(none_ok)
                else:
                    try:
                        tests.append(item > 0 and item % 1 == 0)
                    except TypeError:
                        return False
            return np.all(tests)

        maxshape = _make_iterable(maxshape)
        chunking = _make_iterable(chunking)

        assert _valid_shapes(maxshape, none_ok=True), "maxshape should only contain positive integers or None"
        assert _valid_shapes(chunking, none_ok=False), "chunking should only contain positive integers"

        valid_compressions = [None, 'gzip', 'lzf']
        if compression not in valid_compressions:
            raise ValueError('valid values for compression are: {}'.format(valid_compressions))

        if np.all([_ is None for _ in [data, maxshape]]):
            raise ValueError('both data and maxshape cannot be None')

        if data is not None:
            data = np.array(data)

        if maxshape is not None:
            if data is not None:
                if len(data.shape) != len(maxshape):
                    raise ValueError('Maxshape should have same number of dimensions as data')
                for d_size, m_size in zip(data.shape, maxshape):
                    if m_size is not None:
                        if m_size < d_size:
                            raise ValueError('maxshape should not be smaller than the data shape')
            else:
                if np.any([item is None for item in maxshape]):
                    raise ValueError('maxshape should not have any None values when data is not provided')

        if chunking is not None:
            for item in chunking:
                if item is None:
                    raise ValueError('chunking should not have None values at any dimension')

            if maxshape is not None:
                data_shape = maxshape
            else:
                data_shape = data.shape
            if len(data_shape) != len(chunking):
                raise ValueError('chunking should have the same number of dimensions as either maxshape or data')
            # Now, they have the same number of dimensions:
            # make sure that all its values are less than equal to the size of the data
            for ch, mx in zip(chunking, data_shape):
                if mx is not None:
                    if ch > mx:
                        raise ValueError('chunking shape ({}) must be less than or equal to the data shape ({}) in all '
                                         'dimensions'.format(chunking, data_shape))

        if isinstance(dtype, (str, unicode)):
            dtype = np.dtype(dtype)

        if data is not None:
            if dtype is None:
                # inherit dtype from data by default
                dtype = data.dtype
            """   
            else:
                # cast data? or will h5py take care of this?
                data = dtype(data)
            """

        self.data = data
        self.dtype = dtype
        self.compression = compression
        self.chunking = chunking
        self.resizable = resizable
        self.maxshape = maxshape

    def __getitem__(self, item):
        return self.data[item]


class EmptyMicroDataset(MicroDataset):

    def __init__(self, name, maxshape, dtype=None, compression=None, chunking=None, parent=None, attrs=None):
        """
        Parameters
        ----------
        name : String
            Name of the dataset
        maxshape : tuple of ints
            Maximum size in each axis this dataset is expected to be
        dtype : datatype, (optional)
            typically a datatype of a numpy array =None
        compression : (Optional) String
            See h5py compression. Leave as 'gzip' as a default mode of compression
        chunking : (Optional) tuple of ints
            Chunking in each dimension of the dataset. If not provided,
            default chunking is used by h5py when writing this dataset
        parent : (Optional) String
                HDF5 path to the parent of this object. This value is overwritten
                when this dataset is made the child of a datagroup.
        attrs : dict (Optional). Default = None
            Attributes to be attached to the h5py.Dataset object

        Examples
        --------
        >>> ds_empty = EmptyMicroDataset('Empty', (128,16384), dtype=np.float16, chunking=(1,16384), compression='gzip')

        """
        super(EmptyMicroDataset, self).__init__(name, None, dtype=dtype, compression=compression, chunking=chunking,
                                                parent=parent, resizable=False, maxshape=maxshape, attrs=attrs)


class ExpandableMicroDataset(MicroDataset):

    def __init__(self, name, data, dtype=None, compression=None, chunking=None, parent=None, maxshape=None, attrs=None):
        """
        Parameters
        ----------
        name : String
            Name of the dataset
        data : Object
            See supported objects in h5py
        dtype : datatype,
            typically a datatype of a numpy array =None
        compression : (Optional) String
            See h5py compression. Leave as 'gzip' as a default mode of compression
        chunking : (Optional) tuple of ints
            Chunking in each dimension of the dataset. If not provided,
            default chunking is used by h5py when writing this dataset
        parent : (Optional) String
                HDF5 path to the parent of this object. This value is overwritten
                when this dataset is made the child of a datagroup.
        maxshape : (Optional) tuple of ints
            Maximum size in each axis this dataset is expected to be
            if this parameter is provided, io will ONLY allocate space.
            Make sure to specify the dtype appropriately. The provided data will be ignored
        attrs : dict (Optional). Default = None
            Attributes to be attached to the h5py.Dataset object

        Examples
        --------
        >>> ds_raw_data = ExpandableMicroDataset('Raw_Data', np.zeros(shape=(1,16384), dtype=np.complex64),
        >>>                            chunking=(1,16384), resizable=True, compression='gzip')
        """
        super(ExpandableMicroDataset, self).__init__(name, data, dtype=dtype, compression=compression, resizable=True,
                                                     chunking=chunking, parent=parent, maxshape=maxshape, attrs=attrs)
