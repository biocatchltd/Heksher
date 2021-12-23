Setting Types
========================

Every setting has a type, which determines which values it can hold. Each setting type has a string representation,
which is used to describe the type in the HTTP API.

.. note::

    Internally, all setting values are JSON values. However, it is up to user libraries to interpret these values
    into their local environment's proper types (for example, a setting of type `Flag`_ is stored internally as a JSON
    array, but in python may be interpreted as a frozen set).

.. _primitive:

Primitive Types: int, float, str, bool
---------------------------------------------------

Settings of these types can hold any value of the appropriate type.

* ``int``: an integer
* ``float``: a floating point number
* ``str``: a string
* ``bool``: a boolean

Primitive From a Closed List: Enum[...]
---------------------------------------
Setting values of type ``Enum[...]`` can only hold **one** value from the list of allowed values.
For example, a setting of type ``Enum["red","green","blue"]`` can only hold the values ``"red"``, ``"green"``, or
``"blue"``.

The values inside the list must be `primitive`_, but they do not need to all be the same type. Therefore the type
``Enum[0, 1, "other", false]`` is valid, but ``Enum[0, 1, [0,1]]`` is not.

.. _enum order invariance:

.. note::

    Both the Enum and the `Flag`_ types are order-invariant, meaning that ``Enum[0,1,2]`` is equal to ``Enum[2,1,0]``.
    However, for convenience, the order of the values in the list is always returned in alphabetical order.

    .. code-block:: console

        PUT /api/v1/settings/declare
        {
            "name": "my_setting",
            "type": "Enum[false, \"maybe\", true]",
            ...
        }
        200 {...}

        GET /api/v1/settings/my_setting
        200 {
            "type": "Enum[\"maybe\",false,true]",
            ...
        }

.. _Flag:

Subset of a Closed List: Flag[...]
------------------------------------
Setting values of type ``Flag[...]`` can hold a list of values that are in the list of allowed values. In effect, they
hold a subset of the allowed values. For example, a setting of type ``Flag["red", "green", "blue"]`` may be set to any
of these values:


    * ``"red", "green", "blue"``
    * ``"green", "blue"``
    * ``"red", "blue"``
    * ``"red", "green"``
    * ``"blue"``
    * ``"green"``
    * ``"red"``
    * ``()`` (an empty subset)

The values inside the list must be `primitive`_, but they do not need to all be the same type. Therefore the type
``Flag[0, 1, "other", false]`` is valid, but ``Flag[0, 1, [0,1]]`` is not.

.. note::

    See `enum order invariance`_

Generic Sequence: Sequence<...>
----------------------------------
Setting values of type ``Sequence<T>`` can hold an array of values of the specified type. For example, a setting
of type ``Sequence<int>`` can hold any array of integers.

Sequences can be of any type, even of other sequences. For example, a setting of type
``Sequence<Sequence<Enum["red", "green", "blue"]>>`` can hold any array of arrays of the values ``"red"``, ``"green"``,
or ``"blue"`` (so an example value might be ``[["red", "blue", "green"], ["red", "red"], [], ["green"]]``).

Generic Mappings: Mappings<...>
----------------------------------
Setting values of type ``Mappings<T>`` can hold a dictionary that maps strings to values of the specified type.
For example, a setting of type ``Mappings<int>`` can hold any dictionary mapping strings to integers.

Mappings can be of any type, even of other mappings. For example, a setting of type ``Mapping<Mapping<int>>`` can
hold any dictionary mapping strings to dictionaries that map strings to integers.

Type Order
----------

Setting types have a partial ordering over them. This when we want to safely change a setting's type. We say that type
A is a supertype of type B if every value that can be stored in type B can also be stored in type A. This will help us
when :ref:`declaring settings <api:POST /api/v1/settings/declare>`.

Examples:

* ``float`` is a supertype of ``int``
* ``Sequence<float>`` is a supertype of ``Sequence<int>``
* ``Enum[0,1,2]`` is a supertype of ``Enum[0,1]``

This is a `non-strict partial order <https://en.wikipedia.org/wiki/Partially_ordered_set#Non-strict_partial_order>`_
(reflexive, antisymmetric and transitive).

.. note::

    This definition applies to the conceptual values of the setting types, not it's internal JSON representation.
    For example, a setting of type ``Sequence<int>`` is not supertype of ``Flags[0, 1, 2]``, even though the ``Flags``
    will always be represented as an array of ints internally. This also means that ``Enum[true, false, "other"]`` is
    not a supertype of ``bool``.

