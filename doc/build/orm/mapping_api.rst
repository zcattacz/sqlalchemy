
.. currentmodule:: sqlalchemy.orm

Class Mapping API
=================

.. autoclass:: registry
    :members:

.. autofunction:: add_mapped_attribute

.. autofunction:: declarative_base

.. autofunction:: declarative_mixin

.. autofunction:: as_declarative

.. autofunction:: mapped_column

.. autoclass:: declared_attr

    .. attribute:: cascading

        Mark a :class:`.declared_attr` as cascading.

        This is a special-use modifier which indicates that a column
        or MapperProperty-based declared attribute should be configured
        distinctly per mapped subclass, within a mapped-inheritance scenario.

        .. warning::

            The :attr:`.declared_attr.cascading` modifier has several
            limitations:

            * The flag **only** applies to the use of :class:`.declared_attr`
              on declarative mixin classes and ``__abstract__`` classes; it
              currently has no effect when used on a mapped class directly.

            * The flag **only** applies to normally-named attributes, e.g.
              not any special underscore attributes such as ``__tablename__``.
              On these attributes it has **no** effect.

            * The flag currently **does not allow further overrides** down
              the class hierarchy; if a subclass tries to override the
              attribute, a warning is emitted and the overridden attribute
              is skipped.  This is a limitation that it is hoped will be
              resolved at some point.

        Below, both MyClass as well as MySubClass will have a distinct
        ``id`` Column object established::

            class HasIdMixin:
                @declared_attr.cascading
                def id(cls):
                    if has_inherited_table(cls):
                        return Column(
                            ForeignKey('myclass.id'), primary_key=True
                        )
                    else:
                        return Column(Integer, primary_key=True)

            class MyClass(HasIdMixin, Base):
                __tablename__ = 'myclass'
                # ...

            class MySubClass(MyClass):
                ""
                # ...

        The behavior of the above configuration is that ``MySubClass``
        will refer to both its own ``id`` column as well as that of
        ``MyClass`` underneath the attribute named ``some_id``.

        .. seealso::

            :ref:`declarative_inheritance`

            :ref:`mixin_inheritance_columns`

    .. attribute:: directive

        Mark a :class:`.declared_attr` as decorating a Declarative
        directive such as ``__tablename__`` or ``__mapper_args__``.

        The purpose of :attr:`.declared_attr.directive` is strictly to
        support :pep:`484` typing tools, by allowing the decorated function
        to have a return type that is **not** using the :class:`_orm.Mapped`
        generic class, as would normally be the case when :class:`.declared_attr`
        is used for columns and mapped properties.  At
        runtime, the :attr:`.declared_attr.directive` returns the
        :class:`.declared_attr` class unmodified.

        E.g.::

          class CreateTableName:
              @declared_attr.directive
              def __tablename__(cls) -> str:
                  return cls.__name__.lower()

        .. versionadded:: 2.0

        .. seealso::

            :ref:`orm_mixins_toplevel`

            :class:`_orm.declared_attr`



.. autoclass:: DeclarativeBaseNoMeta
    :members:

.. autoclass:: DeclarativeBase
    :members:

.. autofunction:: has_inherited_table

.. autofunction:: synonym_for

.. autofunction:: object_mapper

.. autofunction:: class_mapper

.. autofunction:: configure_mappers

.. autofunction:: clear_mappers

.. autofunction:: sqlalchemy.orm.util.identity_key

.. autofunction:: polymorphic_union

.. autoclass:: Mapper
   :members:


.. autoclass:: MappedAsDataclass
    :members:
