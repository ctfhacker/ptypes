# ptypes

## Tutorial

We need to implement the following structs using `ptypes`.

```
// Int has type 0
struct Int {
    char type;
    int length;
    int num;
}

// Str has type 1
struct Str {
    char type;
    int length;
    char[] string;
}

// List has type 2
struct List {
    char type,
    int length,
    int num_of_elements,
    union List {
        Int i;
        Str s;
        List l;
    } list[num_of_elements]
}
```

The `Int` struct in `ptypes` looks like the following

```
class Int(pstruct.type):
    _fields_ = [
        (pint.uint8_t, 'type'),
        (pint.uint32_t, 'length'), 
        (pint.uint32_t, 'num'); 
    ]
```

Note the `_fields_` attribute of the class contains a list of tuples where the first element is a type (or a functor as we will see later) and the second element is the name of the field.

In this case, we simply have a 8 bit field, followed by two 32 bit fields. In order to reduce typing, we can create alias classes for the 8 and 32 bit fields:

```
class u8(pint.uint8_t): pass
class u32(pint.uint32_t): pass

class Int(pstruct.type):
    _fields_ = [
        (u8, 'type'),
        (u32, 'length'), 
        (u32, 'num'); 
    ]
```

The `Str` struct can be created in a similar manner:

```
class Str(pstruct.type):
    _fields_ = [
        (u8, 'type'),
        (u32, 'length'), 
        (pstr.string, 'string'); 
    ]
```

Here, instead of the normal `8` or `32` bit field, we use a new class `pstr.string`, which provides us a string.

Before we get too far into the mix, we notice that all of our structs have the same format where the first byte is the `type` and the next 4 bytes are the length of the struct. We can abstract that away using a wrapper class.

```
class general(pstruct.type):
    _fields_ = [
        (u8, 'type'),
        (u32, 'length'),
        (__data, 'data')
    ]
```

Notice the last parameter is of type `__data`. This will be a function that we will define int he `general` class itself. When called, `__data` will return the correct type based on the current `type` being parsed by `ptypes`.

In order to lookup structs based on their type, we need to create a definition for the type of `Items` we have. For now, we can implement the easy `Int` and `Str` structs.

```
class GenericItem(ptype.definition):
    cache = {}

@GenericItem.define
class Int(u32):
    type = 0 # Note: the `type` parameter is a requirement and cannot be renamed

@GenericItem.define
class Str(pstr.string):
    type = 1 # Note: the `type` parameter is a requirement and cannot be renamed
```

The `GenericItem.define` decorator will register the current class with the `GenericItem` and can be retrieved using the `GenericItem.lookup` method.

```
class general(pstruct.type):
    def __data(self):
        item = GenericItem.lookup(self['type'].li.int())    
        return item
```

We see in the `__data` function that `self` already contains a value in `type`. In order to retreive the actual value in `type`, we need to `load` the value and then retreive the `int` representation. The `lookup` function then returns the class that has the `type` requested. Note: this is not an instance of the class, but the raw class itself.

The `Int` struct is a static struct, but the `Str` struct needs to be dynamically allocated based on the size of the given string. Since the `length` field should contain how many bytes the string contains, we need to dynamically set this value after retreiving it from `lookup`.

```
class general(pstruct.type):
    def __data(self):
        item = GenericItem.lookup(self['type'].li.int())    
        if issubclass(item, pstr.string):
            item = dyn.clone(item, length=self['length'].li.int()-5)
        return item
```

Here we create a copy of the `Str` class and set its length to the given length minus 5 (type is one byte, length is 4 bytes, 1 + 4 = 5). The returned type now has its proper length set.

## Basic parsing

Now that we have our basic types created, let's try to use them in parsing a sample.

```
if __name__ == '__main__':
    test_int = '\x00\x09\x00\x00\x00\x78\x56\x34\x12'
    a = general(source=ptypes.provider.string(test_int))
    a = a.l
    print(a)
```

We create a sample `Int` and create a `general` ptype with its source as a string provided by us. `a = a.l` loads the current object using the provided source and then we `print` the result to the screen.

```
<class __main__.general> 'unnamed_1078c80c0' {unnamed=True}
[0] <instance __main__.u8 'type'> 0x00 (0)
[1] <instance __main__.u32 'length'> 0x00000009 (9)
[5] <instance __main__.Int 'data'> 0x12345678 (305419896)
```

We are shown a basic output from ptypes. The number in the `[]` shows the offset in the source that the given struct element is at as well as a brief description of the element itself.

We can also access various pieces of the ptype as well:

```
print("Type", a['type'])
print("Data", a['data'])

('Type', [0] <instance __main__.u8 'type'> 0x00 (0))
('Data', [5] <instance __main__.Int 'data'> 0x12345678 (305419896))
```

Sources can also come from files as well.

```
test_str = '\x01\x0b\x00\x00\x00HELLO\0'
with open('test_str', 'w') as f:
    f.write(test_str)

a = general(source=ptypes.provider.file('test_str'))
a = a.l
print(a)
```

Here we write a sample file to disk and then use it as a source to create a `Str` ptype.

```
<class __main__.general> 'unnamed_1078d99f0' {unnamed=True}
[0] <instance __main__.u8 'type'> 0x01 (1)
[1] <instance __main__.u32 'length'> 0x0000000b (11)
[5] <instance c(__main__.Str<char_t>) 'data'> u'HELLO'
```

## Basic Creation

Sometimes we also want to create various structures using ptypes.

```
b = general().alloc(type=Int.type, data=0xdeadbeef)
b['length'].set(b.size())
print(b)
```

Here we create a `general` object and then allocate the object with a type of `Int` with its number as `0xdeadbeef`. Ptypes doesn't know how to automatically fill in the `length` of the struct, so we set the length to the size of the object.

```
<class __main__.general> 'unnamed_102c2eec0' {unnamed=True}
[0] <instance __main__.u8 'type'> 0x00 (0)
[1] <instance __main__.u32 'length'> 0x00000009 (9)
[5] <instance __main__.Int 'data'> 0xdeadbeef (3735928559)
```

Since the `Str` struct contains a dynamic element, we must first create our underlying `pstr.string`. To do this, we must first set the `length` to that of our wanted string and the set the contents to our string.

```
s = "hello world"
mystr = Str(length=len(s)).set(s)
```

Once we have the string created, we can set the string as the data for the `general` struct. Lastly, we set the `length` of the struct to the size of the object.

```
c = general().alloc(type=Str.type, data=mystr)
c['length'].set(c.size())
print(c)
```

```
<class __main__.general> 'unnamed_101f144b0' {unnamed=True}
[0] <instance __main__.u8 'type'> 0x01 (1)
[1] <instance __main__.u32 'length'> 0x00000010 (16)
[5] <instance __main__.Str<char_t> 'data'> u'hello world'
```

## List Struct

Now that we have a basic blocks of `Int` and `Str` finished, let's see how we can create the `List` struct, which is essentially a list of `Int`s and `Str`s.

We first create a new `GenericItem` type for the `List`.

```
@GenericItem.define
class List(pstruct.type):
    type = 2
```

Now, the `List` struct actually contains a few more elements specific to a `List`, namely the `num_of_elements` and the actual list itself. These can be added to its own `_fields_` attribute.

```
@GenericItem.define
class List(pstruct.type):
    type = 2

    def __data(self):
        return dyn.array(general, s['num_of_elements'].li.int())

    _fields_ = [
        (u32, 'num_of_elements'),
        (__data, 'list')
    ]
```

We create the `num_of_elements` field for the `List` as well as a dynamic array containing `num_of_element` many elements of type `general`. This could also be written in a shorter one liner using a `lambda` expression.

```
@GenericItem.define
class List(pstruct.type):
    type = 2

    _fields_ = [
        (u32, 'num_of_elements'),
        (lambda s: dyn.array(general, s['num_of_elements'].li.int()): 'list')
    ]
```

Now that we have our list, let's test parsing a list of `Ints`

```
test_ints = '\x02\x24\x00\x00\x00\x03\x00\x00\x00' + '\x00\x09\x00\x00\x00\x78\x56\x34\x12'*3
x = general(source=ptypes.provider.string(test_ints))
x = x.l

print(x)
print(x['data'])
for index, item in enumerate(x['data']['list']):
    print("Index: {}".format(index))
    print(item)
```

Here we pretend to have read this struct from the wire and saved it in the `test_ints` variable. As before, we use the `provider.string` to load the source into our `general` ptype. From here we print the object and then each element in our parsed `list`.

```
<class __main__.List> 'data'
[5] <instance __main__.u32 'num_of_elements'> 0x00000003 (3)
[9] <instance dynamic.array(__main__.general,3) 'list'> __main__.general[3] "\x00\x09\x00\x00\x00\x78\x56\x34\x12\x00\x09\x00\x00\x00\x78\x56\x34\x12\x00\x09\x00\x00\x00\x78\x56\x34\x12"

Index: 0
<class __main__.general> '0'
[9] <instance __main__.u8 'type'> 0x00 (0)
[a] <instance __main__.u32 'length'> 0x00000009 (9)
[e] <instance __main__.Int 'data'> 0x12345678 (305419896)

Index: 1
<class __main__.general> '1'
[12] <instance __main__.u8 'type'> 0x00 (0)
[13] <instance __main__.u32 'length'> 0x00000009 (9)
[17] <instance __main__.Int 'data'> 0x12345678 (305419896)

Index: 2
<class __main__.general> '2'
[1b] <instance __main__.u8 'type'> 0x00 (0)
[1c] <instance __main__.u32 'length'> 0x00000009 (9)
[20] <instance __main__.Int 'data'> 0x12345678 (305419896)
```

And just to confirm the parsing of a list of strings.

```
test_ints = '\x02\xff\x00\x00\x00\x05\x00\x00\x00' + test_int*3 + test_str*2
x = general(source=ptypes.provider.string(test_ints))
x = x.l
print(x)
print(x['data'])
for index, item in enumerate(x['data']['list']):
    print("Index: {}".format(index))
    print(item)
```

```
<class __main__.general> 'unnamed_103ed0de0' {unnamed=True}
[0] <instance __main__.u8 'type'> 0x02 (2)
[1] <instance __main__.u32 'length'> 0x000000ff (255)
[5] <instance __main__.List 'data'> "\x05\x00\x00\x00\x00\x09\x00\x00\x00\x78\x56\x34\x12\x00\x09\x00\x00\x00\x78\x56\x34\x12\x00\x09\x00\x00\x00\x78\x56\x34\x12\x01\x0b\x00\x00\x00\x48\x45\x4c\x4c\x4f\x00\x01\x0b\x00\x00\x00\x48\x45\x4c\x4c\x4f\x00"

<class __main__.List> 'data'
[5] <instance __main__.u32 'num_of_elements'> 0x00000005 (5)
[9] <instance dynamic.array(__main__.general,5) 'list'> __main__.general[5] "\x00\x09\x00\x00\x00\x78\x56\x34\x12\x00\x09\x00\x00\x00\x78\x56\x34\x12\x00\x09\x00\x00\x00\x78\x56\x34\x12\x01\x0b\x00\x00\x00\x48\x45\x4c\x4c\x4f\x00\x01\x0b\x00\x00\x00\x48\x45\x4c\x4c\x4f\x00"

Index: 0
<class __main__.general> '0'
[9] <instance __main__.u8 'type'> 0x00 (0)
[a] <instance __main__.u32 'length'> 0x00000009 (9)
[e] <instance __main__.Int 'data'> 0x12345678 (305419896)

Index: 1
<class __main__.general> '1'
[12] <instance __main__.u8 'type'> 0x00 (0)
[13] <instance __main__.u32 'length'> 0x00000009 (9)
[17] <instance __main__.Int 'data'> 0x12345678 (305419896)

Index: 2
<class __main__.general> '2'
[1b] <instance __main__.u8 'type'> 0x00 (0)
[1c] <instance __main__.u32 'length'> 0x00000009 (9)
[20] <instance __main__.Int 'data'> 0x12345678 (305419896)

Index: 3
<class __main__.general> '3'
[24] <instance __main__.u8 'type'> 0x01 (1)
[25] <instance __main__.u32 'length'> 0x0000000b (11)
[29] <instance c(__main__.Str<char_t>) 'data'> u'HELLO'

Index: 4
<class __main__.general> '4'
[2f] <instance __main__.u8 'type'> 0x01 (1)
[30] <instance __main__.u32 'length'> 0x0000000b (11)
[34] <instance c(__main__.Str<char_t>) 'data'> u'HELLO'
```

We can also modify these objects in place. Let's say we want to replace the second element with a string that says 'hello world'.

```
s = "hello world"
mystr = Str(length=len(s)).set(s)
c = general().alloc(type=Str.type, data=mystr)

x['data']['list'][1] = c
x.setoffset(x.getoffset(), recurse=True)

for index, item in enumerate(x['data']['list']):
    print("Index: {}".format(index))
    print(item)
```

We can print this same as before and see that our list now has a new ptype in the second element.

```
<class __main__.general> 'unnamed_1008dede0' {unnamed=True}
[0] <instance __main__.u8 'type'> 0x02 (2)
[1] <instance __main__.u32 'length'> 0x00000041 (65) # OUTPUT HAS CHANGED
[5] <instance __main__.List 'data'> "\x05\x00\x00\x00\x00\x09\x00\x00\x00\x78\x56\x34\x12\x01\x00\x00\x00\x00\x68\x65\x6c\x6c\x6f\x20\x77\x6f\x72\x6c\x64\x00\x09\x00\x00\x00\x78\x56\x34\x12\x01\x0b\x00\x00\x00\x48\x45\x4c\x4c\x4f\x00\x01\x0b\x00\x00\x00\x48\x45\x4c\x4c\x4f\x00"

<class __main__.List> 'data'
[5] <instance __main__.u32 'num_of_elements'> 0x00000005 (5)
[9] <instance dynamic.array(__main__.general,5) 'list'> __main__.general[5] "\x00\x09\x00\x00\x00\x78\x56\x34\x12\x01\x00\x00\x00\x00\x68\x65\x6c\x6c\x6f\x20\x77\x6f\x72\x6c\x64\x00\x09\x00\x00\x00\x78\x56\x34\x12\x01\x0b\x00\x00\x00\x48\x45\x4c\x4c\x4f\x00\x01\x0b\x00\x00\x00\x48\x45\x4c\x4c\x4f\x00"

Index: 0
<class __main__.general> '0'
[9] <instance __main__.u8 'type'> 0x00 (0)
[a] <instance __main__.u32 'length'> 0x00000009 (9)
[e] <instance __main__.Int 'data'> 0x12345678 (305419896)

Index: 1
<class __main__.general> '1'
[12] <instance __main__.u8 'type'> 0x01 (1)
[13] <instance __main__.u32 'length'> 0x00000000 (0)
[17] <instance __main__.Str<char_t> 'data'> u'hello world'

Index: 2
<class __main__.general> '2'
[1b] <instance __main__.u8 'type'> 0x00 (0)
[1c] <instance __main__.u32 'length'> 0x00000009 (9)
[20] <instance __main__.Int 'data'> 0x12345678 (305419896)

...
```

Lastly, we can print a `hexdump` of the final object as well or `serialize` if we need a bytearray of the object.

```
print(x.hexdump())

0000  02 41 00 00 00 05 00 00  00 00 09 00 00 00 78 56  .A............xV
0010  34 12 01 00 00 00 00 68  65 6c 6c 6f 20 77 6f 72  4......hello wor
0020  6c 64 00 09 00 00 00 78  56 34 12 01 0b 00 00 00  ld.....xV4......
0030  48 45 4c 4c 4f 00 01 0b  00 00 00 48 45 4c 4c 4f  HELLO......HELLO
0040  00                                                .               

print(x.serialize())
A	xV4hello world	xV4HELLOHELLO
```
