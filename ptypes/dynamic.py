"""Utilities for creating or modifying types dynamically.

When defining the various complex-data structures that can exist within an
application, a lot of types are dynamically generated. Dynamically generated can
mean either having a variable size, a type that's based on an enumeration, an
encoding based on the value of a particular field, etc. This module contains a
few utilities that can be used for defining or transforming types as the data
structure is decoded or loaded.

Within this module are the following functions:

    block -- Define a block of a specific size
    blockarray -- Define an array of elements up to a particular size.
    align -- A type that will align a structure to a specified alignment.
    array -- Define an array with it's subtype and size.
    clone -- Clone a type into a new type with the specified attributes and values.
    pointer -- Return a pointer type that points to another type.
    rpointer -- Return a pointer type that's relative to another object.
    opointer -- Return a pointer type that's offset is transformed.

Also within this module is a type that's used to define a union. A union is a
root type that can be transformed into a number of various types. The union
interface is used similarly to a pstruct.type. When using a dynamic.union type,
the root type can be defined as a property named `.root`. If this property is
not defined, the type will be inferred from the largest field that is defined.
Once a union is instantiated, the different subtypes can be accessed as if they
are field names of a pstruct.type.

An example of this definition:

    class union(dynamic.union):
        _fields_ = [
            (subtype1, 'a'),
            (subtype2, 'b'),
            (subtype3, 'c'),
        ]

Example usage:
# create a block type that's 0x100 bytes in size
    from ptypes import dynamic
    type = dynamic.block(0x100)

# create an array type for a block that's 0x40 bytes
    from ptypes import pint,dyn
    type = dyn.blockarray(pint.uint32_t, 0x40)

# create a structure with field1 aligned to offset 4
    from ptypes import pstruct,pint,dyn
    class type(pstruct.type):
        _fields_ = [
            (pint.uint8_t, 'field1'),
            (dyn.align(4), 'align1'),
            (pint.uint32_t, 'field2'),
        ]

# create an array type of 12 uint32_t's
    type = dyn.array(pint.uint32_t, 12)

# clone a pstr.string type, modifying the length field to 8 characters.
    from ptypes import pstr,dyn
    type = dyn.clone(pstr.string, length=8)

# create a pointer to a uint32
    from ptypes import pint,pstr,dyn
    type = dyn.pointer(pint.uint32_t)

# create a pointer to a szstring relative to a parent element that's an array
    type = dyn.rpointer(pstr.szstring, lambda s: s.getparent(parray.type))

# create a pointer to a uint32 relative to the current pointer's value + 0x100
    type = dyn.opointer(pint.uint32_t, lambda s: s.int() + 0x100)

# create a union type backed by an array of 4 uint32 types
    from ptypes import dynamic,pint,pstr
    class type(dynamic.union):
        _value_ = dynamic.array(pint.uint32_t, 4)
        _fields_ = [
            (dyn.block(16), 'block'),
            (dyn.array(pint.uint16_t, 8), 'ushort'),
            (dyn.clone(pstr.wstring, length=8), 'widestring'),
        ]
"""
import six,operator

from . import ptype,parray,pstruct,config,error,utils,provider,pint
Config = config.defaults
Log = Config.log.getChild(__name__[len(__package__)+1:])
__all__ = 'block,blockarray,align,array,clone,pointer,rpointer,opointer,union'.split(',')

## FIXME: might want to raise an exception or warning if we have too large of a block
def block(size, **kwds):
    """Returns a ptype.block type with the specified ``size``"""
    if not isinstance(size, six.integer_types):
        t = ptype.block(length=size)
        raise error.UserError(t, 'block', message='Argument size must be integral : {:s} -> {!r}'.format(size.__class__, size))

    if size < 0:
        t = ptype.block(length=size)
        Log.error('block : {:s} : Invalid argument size={:d} cannot be < 0. Defaulting to 0'.format(t.typename(), size))
        size = 0

    def classname(self):
        return 'dynamic.block({:d})'.format(self.blocksize())
    kwds.setdefault('classname', classname)
    kwds.setdefault('__module__', 'ptypes.dynamic')
    kwds.setdefault('__name__', 'block')
    return clone(ptype.block, length=size, **kwds)

def blockarray(type, size, **kwds):
    """Returns a parray.block with the specified ``size`` and ``type``"""
    if not isinstance(size, six.integer_types):
        t = parray.block(_object_=type)
        raise error.UserError(t, 'blockarray', message='Argument size must be integral : {:s} -> {!r}'.format(size.__class__, size))

    if size < 0:
        t = parray.block(_object_=type)
        Log.error('blockarray : {:s} : Invalid argument size={:d} cannot be < 0. Defaulting to 0'.format(t.typename(),size))
        size = 0

    class blockarray(parray.block):
        _object_ = type
        def blocksize(self):
            return size

        def classname(self):
            t = type.typename() if ptype.istype(type) else type.__name__
            return 'dynamic.blockarray({:s},{:d})'.format(t, self.blocksize())
    blockarray.__module__ = 'ptypes.dynamic'
    blockarray.__name__ = 'blockarray'
    blockarray.__getinitargs__ = lambda s: (type,size)
    return blockarray

def align(size, **kwds):
    '''return a block that will align a structure to a multiple of the specified number of bytes'''
    if not isinstance(size, six.integer_types):
        t = ptype.type(length=0)
        raise error.UserError(t, 'align', message='Argument size must be integral : {:s} -> {!r}'.format(size.__class__, size))

    # methods to get assigned
    def repr(self, **options): return self.summary(**options)
    def blocksize(self):
        parent = self.parent
        if parent is None or self not in parent.value:
            return 0
        idx = parent.value.index(self)
        offset = parent.getoffset()+sum(n.blocksize() for n in parent.value[:idx])
        return (-offset) & (size-1)
    getinitargs = lambda s: (type,kwds)

    # if alignment is undefined
    if kwds.get('undefined', False):
        class result(ptype.undefined):
            def classname(self): return 'dynamic.undefined({:d}, size={:d})'.format(size,self.blocksize())
        result.repr,result.blocksize,result.__getinitargs__ = repr,blocksize,getinitargs
        result.__module__,result.__name__ = 'ptypes.dynamic','undefined'
        return result

    # otherwise, padding
    class result(ptype.block):
        initializedQ = lambda self: self.value is not None
        def classname(self): return 'dynamic.align({:d}, size={:d})'.format(size,self.blocksize())
    result.repr,result.blocksize,result.__getinitargs__ = repr,blocksize,getinitargs
    result.__module__,result.__name__ = 'ptypes.dynamic','align'
    return result

## FIXME: might want to raise an exception or warning if we have too large of an array
def array(type, count, **kwds):
    '''
    returns an array of the specified length containing elements of the specified type
    '''
    count = int(count)
    if not isinstance(count, six.integer_types):
        t = parray.type(_object_=type,length=count)
        raise error.UserError(t, 'array', message='Argument count must be integral : {:s} -> {!r}'.format(count.__class__, count))

    if count < 0:
        t = parray.type(_object_=type,length=count)
        Log.error('dynamic.array : {:s} : Invalid argument count={:d} cannot be < 0. Defaulting to 0.'.format(t.typename(), count))
        count = 0

    if Config.parray.max_count > 0 and count > Config.parray.max_count:
        t = parray.type(_object_=type,length=count)
        if Config.parray.break_on_max_count:
            Log.fatal('dynamic.array : {:s} : Requested argument count={:d} is larger than configuration max_count={:d}.'.format(t.typename(), count, Config.parray.max_count))
            raise error.UserError(t, 'array', message='Requested array count={:d} is larger than configuration max_count={:d}'.format(count, Config.parray.max_count))
        Log.warn('dynamic.array : {:s} : Requested argument count={:d} is larger than configuration max_count={:d}.'.format(t.typename(), count, Config.parray.max_count))

    def classname(self):
        obj = type
        t = obj.typename() if ptype.istype(obj) else obj.__name__
        return 'dynamic.array({:s},{:s})'.format(t, str(self.length))

    kwds.setdefault('classname', classname)
    kwds.setdefault('length', count)
    kwds.setdefault('_object_', type)
    kwds.setdefault('__module__', 'ptypes.dynamic')
    kwds.setdefault('__name__', 'array')
    return ptype.clone(parray.type, **kwds)

def clone(cls, **newattrs):
    '''
    Will clone a class, and set its attributes to **newattrs
    Intended to aid with single-line coding.
    '''
    return ptype.clone(cls, **newattrs)

class _union_generic(ptype.container):
    def __init__(self, *args, **kwds):
        super(_union_generic,self).__init__(*args, **kwds)
        self.__fastindex = {}

    def append(self, object):
        """Add an element as part of a union. Return it's index."""
        return self.__append__(object)
    def __append__(self, object):
        name = object.name()

        current = len(self.__object__)
        self.__object__.append(object)

        self.__fastindex[name.lower()] = current
        return current

    # list methods
    def keys(self):
        return [name for name in self.__keys__()]
    def values(self):
        return list(self.__values__())
    def items(self):
        return [(k, v) for k, v in self.__items__()]

    # iterator methods
    def iterkeys(self):
        for name in self.__keys__(): yield name
    def itervalues(self):
        for res in self.__values__(): yield res
    def iteritems(self):
        for k, v in self.__items__(): yield k, v

    # internal dict methods
    def __keys__(self):
        for type, name in self._fields_: yield name
    def __values__(self):
        for res in self.__object__: yield res
    def __items__(self):
        for (_, k), v in zip(self._fields_, self.__object__):
            yield k, v
        return

    def __getindex__(self, name):
        return self.__fastindex[name.lower()]
    def __getitem__(self, name):
        index = self.__getindex__(name)
        return self.__object__[index]

class union(_union_generic):
    """
    Provides a data structure with Union-like characteristics. If the root type
    isn't defined, it is assumed the first type in the union will be the root.

    The hidden `.__object__` property contains a list of the instantiated types
    for each defined field. The `.object` property points to an instance of the
    `.root` property.

    i.e.
    class myunion(dynamic.union):
        _fields_ = [
            (structure1, 'a'),
            (structure2, 'b'),
            (structure3, 'c'),
        ]

    In this example, each field 'a', 'b', and 'c' begin at the same offset. Since
    a root object is not defined, it is determined by the size of the first
    field. If `structure2` or `structure3` is larger than `structure1`, then
    these fields will be left partially uninitialized when accessed.

    i.e.
    class myunion(dynamic.union)::
        _value_ = block(256)
        _fields_ = [
            (dyn.array(uint16_t,64), 'a'),
            (dyn.array(uint8_t,64), 'b'),
        ]

    In this example, the union is backed by a `block(256)` object. This object
    will be used to decode the structures used by field 'a' and field 'b'.
    """
    _value_ = None      # root type. determines block size.
    _fields_ = []       # aliases of root type that will act on the same data
    __object__ = None   # objects associated with each alias
    value = None

    @property
    def object(self):
        if self.value is None:
            return self.__create__()
        return self.value[0]
    o = object

    initializedQ = lambda self: isinstance(self.value, list) and self.value[0].initializedQ() and self.__object__ is not None and len(self.__object__) == len(self._fields_ or [])
    def __choose__(self, objects):
        """Return a ptype.block of a size that contain /objects/"""
        res = self._value_
        if res is None:
            size = max(self.new(t).a.blocksize() for t in objects)
            return clone(ptype.block, length=size)
        return res

    def __create__(self):
        t = self.__choose__(t for t,n in self._fields_)
        res = self.new(t, offset=self.getoffset())
        self.value = [res]

        source = provider.proxy(res)      # each element will write into the offset occupied by value
        self.__object__ = []
        for t,n in self._fields_:
            res = self.new(t, __name__=n, offset=0, source=source)
            self.__append__(res)
        return self.value[0]

    def alloc(self, **attrs):
        res = self.__create__() if self.value is None else self.value[0]
        res.alloc(**attrs)
        map(operator.methodcaller('load', offset=0), self.__object__)
        return self

    def serialize(self):
        return self.value[0].serialize()

    def load(self, **attrs):
        res = self.__create__() if self.value is None else self.value[0]
        res.load(**attrs)
        map(operator.methodcaller('load', offset=0), self.__object__)
        return self

    def commit(self, **attrs):
        return self.object.commit(**attrs)

    def __deserialize_block__(self, block):
        self.value[0].__deserialize_block__(block)
        return self

    def properties(self):
        result = super(union,self).properties()
        if self.initializedQ():
            result['object'] = ['{:s}<{:s}>'.format(v.name(),v.classname()) for v in self.__object__]
        else:
            result['object'] = ['{:s}<{:s}>'.format(n,t.typename()) for t,n in self._fields_]
        return result

    def __getitem__(self, key):
        result = super(union,self).__getitem__(key)
        try:
            result.li
        except error.UserError, e:
            Log.warning("union.__getitem__ : {:s} : Ignoring exception {:s}".format(self.instance(), e))
        return result

    def details(self):
        if not self.initializedQ():
            return self.__details_uninitialized()
        return self.__details_initialized()
    repr = details

    def __details_initialized(self):
        gettypename = lambda t: t.typename() if ptype.istype(t) else t.__name__
        result = []

        # do the root object first
        inst = utils.repr_instance(self.object.classname(), '<object>')
        prop = ','.join('{:s}={!r}'.format(k,v) for k,v in self.object.properties().iteritems())
        result.append('[{:x}] {:s}{:s} {:s}'.format(self.getoffset(), inst, ' {{{:s}}}'.format(prop) if prop else '', self.object.summary()))

        # now try to do the rest of the fields
        for fld, value in map(None, self._fields_, self.__object__ or []):
            t, name = fld or (value.__class__, value.name())
            inst = utils.repr_instance(value.classname(), value.name() or name)
            prop = ','.join('{:s}={!r}'.format(k,v) for k,v in value.properties().iteritems())
            result.append('[{:x}] {:s}{:s} {:s}'.format(self.getoffset(), inst, ' {{{:s}}}'.format(prop) if prop else '', value.summary()))

        if len(result) > 0:
            return '\n'.join(result)
        return '[{:x}] Empty []'.format(self.getoffset())

    def __details_uninitialized(self):
        gettypename = lambda t: t.typename() if ptype.istype(t) else t.__name__
        result = []

        # first the object if it's been allocated
        if self.object is not None:
            inst = utils.repr_instance(self.object.classname(), '<object>')
            prop = ','.join('{:s}={!r}'.format(k,v) for k,v in self.object.properties().iteritems())
            result.append('[{:x}] {:s}{:s} {:s}'.format(self.getoffset(), inst, ' {{{:s}}}'.format(prop) if prop else '', self.object.summary()))
        else:
            result.append('[{:x}] {:s} ???'.format(self.getoffset(), gettypename(self._value_)))

        # now the rest of the fields
        for fld, value in map(None, self._fields_, self.__object__ or []):
            t, name = fld or (value.__class__, value.name())
            if value is None:
                result.append('[{:x}] {:s} {:s} ???'.format(self.getoffset(), utils.repr_class(gettypename(t)), name))
                continue
            inst = utils.repr_instance(value.classname(), value.name() or name)
            prop = ','.join('{:s}={!r}'.format(k,v) for k,v in value.properties().iteritems())
            result.append('[{:x}] {:s}{:s} {:s}'.format(self.getoffset(), inst, ' {{{:s}}}'.format(prop) if prop else '', value.summary() if value.initializedQ() else '???'))

        if len(result) > 0:
            return '\n'.join(result)
        return '[{:x}] Empty []'.format(self.getoffset())

    def blocksize(self):
        return self.object.blocksize()
    def size(self):
        return self.object.size()

    def setposition(self, offset, recurse=False):
        if self.value is not None:
            self.value[0].setposition(offset, recurse=recurse)
        return super(ptype.container, self).setposition(offset, recurse=recurse)
    def getposition(self):
        return super(ptype.container, self).getposition()

union_t = union # alias

def pointer(target, *optional_type, **attrs):
    """pointer(object, type?, **attributes):
    Returns a pointer to the type ``target``.
    object -- specify the type this pointer points to.
    type -- optional argument specifying the base type of the pointer.
    """
    if len(optional_type) > 1:
        raise TypeError('{:s}.pointer takes exactly 1 or 2 arguments ({:d} given)'.format(__name__, 1 + len(optional_type)))
    type = ptype.pointer_t._value_ if len(optional_type) == 0 or optional_type[0] is None else optional_type[0]
    def classname(self):
        return 'dynamic.pointer({:s})'.format(target.typename() if ptype.istype(target) else target.__name__)
#    attrs.setdefault('classname', classname)
    t = ptype.pointer_t._value_ if type is None else type
    res = ptype.clone(t, **attrs)
    return ptype.clone(ptype.pointer_t, _object_=target, _value_=res)

def rpointer(target, *optional, **attrs):
    """rpointer(target, object?, type?, **attributes):
    Returns a pointer to the type ``target`` relative to the specified object.
    target -- specify the type this pointer points to.
    object -- specify the object this pointer is relative to. defaults to self.
    type -- optional argument specifying the base type of the pointer.
    """
    if len(optional) > 2:
        raise TypeError('{:s}.rpointer takes exactly 1 - 3 arguments ({:d} given)'.format(__name__, 1 + len(optional)))
    object = (lambda s: list(s.walk())[-1]) if len(optional) == 0 or optional[0] is None else optional[0]
    def classname(self):
        return 'dynamic.rpointer({:s}, ...)'.format(target.typename() if ptype.istype(target) else target.__name__)
#    attrs.setdefault('classname', classname)
    t = ptype.pointer_t._value_ if len(optional) == 1 or optional[1] is None else optional[1]
    res = ptype.clone(t, **attrs)
    return ptype.clone(ptype.rpointer_t, _object_=target, _baseobject_=object, _value_=res)

def opointer(target, *optional, **attrs):
    """rpointer(target, calculate?, type?, **attributes):
    Returns a pointer relative to the specified offset
    target -- specify the type this pointer points to.
    calculate -- a function taking a single offset used to calculate the new offset.
    type -- optional argument specifying the base type of the pointer.
    """
    if len(optional) > 2:
        raise TypeError('{:s}.opointer takes exactly 1 - 3 arguments ({:d} given)'.format(__name__, 1 + len(optional)))
    calculate = (lambda s,o: o) if len(optional) == 0 or optional[0] is None else optional[0]
    def classname(self):
        return 'dynamic.opointer({:s}, ...)'.format(target.typename() if ptype.istype(target) else target.__name__)
#    attrs.setdefault('classname', classname)
    t = ptype.pointer_t._value_ if len(optional) == 1 or optional[1] is None else optional[1]
    res = ptype.clone(t, **attrs)
    return ptype.clone(ptype.opointer_t, _object_=target, _calculate_=calculate, _value_=res)

if __name__ == '__main__':
    class Result(Exception): pass
    class Success(Result): pass
    class Failure(Result): pass

    TestCaseList = []
    def TestCase(fn):
        def harness(**kwds):
            name = fn.__name__
            try:
                res = fn(**kwds)
                raise Failure
            except Success,e:
                print '%s: %r'% (name,e)
                return True
            except Failure,e:
                print '%s: %r'% (name,e)
            except Exception,e:
                print '%s: %r : %r'% (name,Failure(), e)
            return False
        TestCaseList.append(harness)
        return fn

if __name__ == '__main__':
    import ptypes,zlib
    from ptypes import dynamic,pint,parray,pstruct,config

    ptypes.setsource(ptypes.provider.string('A'*50000))

    string1='ABCD'  # bigendian
    string2='DCBA'  # littleendian

    s1 = 'the quick brown fox jumped over the lazy dog'
    s2 = s1.encode('zlib')

    @TestCase
    def test_dynamic_union_rootstatic():
        class test(dynamic.union):
            _value_ = dynamic.array(pint.uint8_t,4)
            _fields_ = [
                (dynamic.block(4), 'block'),
                (pint.uint32_t, 'int'),
            ]

        a = test(source=ptypes.provider.string('A'*4))
        a=a.l
        if a.object[0].int() != 0x41:
            raise Failure

        if a['block'].size() == 4 and a['int'].int() == 0x41414141:
            raise Success

    @TestCase
    def test_dynamic_alignment():
        class test(pstruct.type):
            _fields_ = [
                (pint.uint32_t, 'u32'),
                (pint.uint8_t, 'u8'),
                (dynamic.align(4), 'alignment'),
                (pint.uint32_t, 'end'),
            ]

        a = test(source=ptypes.provider.string('A'*12))
        a=a.l
        if a.size() == 12:
            raise Success

    @TestCase
    def test_dynamic_pointer_bigendian():
        ptype.setbyteorder(config.byteorder.bigendian)

        s = ptype.provider.string(string1)
        p = dynamic.pointer(dynamic.block(0))
        x = p(source=s).l
        if x.d.getoffset() == 0x41424344 and x.serialize() == string1:
            raise Success

    @TestCase
    def test_dynamic_pointer_littleendian_1():
        ptype.setbyteorder(config.byteorder.littleendian)
        s = ptype.provider.string(string2)

        t = dynamic.pointer(dynamic.block(0))
        x = t(source=s).l
        if x.d.getoffset() == 0x41424344 and x.serialize() == string2:
            raise Success

    @TestCase
    def test_dynamic_pointer_littleendian_2():
        ptype.setbyteorder(config.byteorder.littleendian)
        string = '\x26\xf8\x1a\x77'
        s = ptype.provider.string(string)

        t = dynamic.pointer(dynamic.block(0))
        x = t(source=s).l
        if x.d.getoffset() == 0x771af826 and x.serialize() ==  string:
            raise Success

    @TestCase
    def test_dynamic_pointer_bigendian_deref():
        ptype.setbyteorder(config.byteorder.bigendian)

        s = ptype.provider.string('\x00\x00\x00\x04\x44\x43\x42\x41')
        t = dynamic.pointer(dynamic.block(4))
        x = t(source=s)
        if x.l.d.getoffset() == 4:
            raise Success

    @TestCase
    def test_dynamic_pointer_littleendian_deref():
        ptype.setbyteorder(config.byteorder.littleendian)

        s = ptype.provider.string('\x04\x00\x00\x00\x44\x43\x42\x41')
        t = dynamic.pointer(dynamic.block(4))
        x = t(source=s)
        if x.l.d.getoffset() == 4:
            raise Success

    @TestCase
    def test_dynamic_pointer_littleendian_64bit_deref():
        ptype.setbyteorder(config.byteorder.littleendian)
        t = dynamic.pointer(dynamic.block(4), pint.uint64_t)
        x = t(source=ptype.provider.string('\x08\x00\x00\x00\x00\x00\x00\x00\x41\x41\x41\x41')).l
        if x.l.d.getoffset() == 8:
            raise Success

    @TestCase
    def test_dynamic_array_1():
        v = dynamic.array(pint.int32_t, 4)
        if len(v().a) == 4:
            raise Success

    @TestCase
    def test_dynamic_array_2():
        v = dynamic.array(pint.int32_t, 8)
        i = six.moves.range(0x40,0x40+v.length)
        x = ptype.provider.string(''.join(six.int2byte(x)+'\x00\x00\x00' for x in i))
        z = v(source=x).l
        if z[4].int() == 0x44:
            raise Success

    @TestCase
    def test_dynamic_union_rootchoose():
        class test(dynamic.union):
            _fields_ = [
                (pint.uint32_t, 'a'),
                (pint.uint16_t, 'b'),
                (pint.uint8_t, 'c'),
            ]

        a = test()
        a=a.a
        if a['a'].blocksize() == 4 and a['b'].size() == 2 and a['c'].size() == 1 and a.blocksize() == 4:
            raise Success

if __name__ == '__main__':
    import logging
    ptypes.config.defaults.log.setLevel(logging.DEBUG)

    results = []
    for t in TestCaseList:
        results.append( t() )
