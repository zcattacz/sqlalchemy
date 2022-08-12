.. _loading_columns:

.. currentmodule:: sqlalchemy.orm

===============
Loading Columns
===============

This section presents additional options regarding the loading of columns.

.. _deferred:

Deferred Column Loading
=======================

Deferred column loading allows particular columns of a table be loaded only
upon direct access, instead of when the entity is queried using
:class:`_sql.Select` or :class:`_orm.Query`.  This feature is useful when one wants to avoid
loading a large text or binary field into memory when it's not needed.

Configuring Deferred Loading at Mapper Configuration Time
---------------------------------------------------------

First introduced at :ref:`orm_declarative_column_options` and
:ref:`orm_imperative_table_column_options`, the
:paramref:`_orm.mapped_column.deferred` parameter of :func:`_orm.mapped_column`,
as well as the :func:`_orm.deferred` ORM function may be used to indicate mapped
columns as "deferred" at mapper configuration time.  With this configuration,
the target columns will not be loaded in SELECT statements by default, and
will instead only be loaded "lazily" when their corresponding attribute is
accessed on a mapped instance.   Deferral can be configured for individual
columns or groups of columns that will load together when any of them
are accessed.

In the example below, using :ref:`Declarative Table <orm_declarative_table>`
configuration, we define a mapping that will load each of
``.excerpt`` and ``.photo`` in separate, individual-row SELECT statements when each
attribute is first referenced on the individual object instance::

    from sqlalchemy import Text
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.orm import Mapped
    from sqlalchemy.orm import mapped_column

    class Base(DeclarativeBase):
        pass

    class Book(Base):
        __tablename__ = 'book'

        book_id: Mapped[int] = mapped_column(primary_key=True)
        title: Mapped[str]
        summary: Mapped[str]
        excerpt: Mapped[str] = mapped_column(Text, deferred=True)
        photo: Mapped[bytes] = mapped_column(deferred=True)

A :func:`_sql.select` construct for the above mapping will not include
``excerpt`` and ``photo`` by default::

    >>> from sqlalchemy import select
    >>> print(select(Book))
    SELECT book.book_id, book.title, book.summary
    FROM book

When an object of type ``Book`` is loaded by the ORM, accessing the
``.excerpt`` or ``.photo`` attributes will instead :term:`lazy load` the
data from each column using a new SQL statement.

When using :ref:`Imperative Table <orm_imperative_table_configuration>`
or fully :ref:`Imperative <orm_imperative_mapping>` configuration, the
:func:`_orm.deferred` construct should be used instead, passing the
target :class:`_schema.Column` object to be mapped as the argument::

    from sqlalchemy import Column, Integer, LargeBinary, String, Table, Text
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.orm import deferred


    class Base(DeclarativeBase):
        pass


    book = Table(
        "book",
        Base.metadata,
        Column("book_id", Integer, primary_key=True),
        Column("title", String),
        Column("summary", String),
        Column("excerpt", Text),
        Column("photo", LargeBinary),
    )


    class Book(Base):
        __table__ = book

        excerpt = deferred(book.c.excerpt)
        photo = deferred(book.c.photo)


Deferred columns can be associated with a "group" name, so that they load
together when any of them are first accessed.  When using
:func:`_orm.mapped_column`, this group name may be specified using the
:paramref:`_orm.mapped_column.deferred_group` parameter, which implies
:paramref:`_orm.mapped_column.deferred` if that parameter is not already
set.  When using :func:`_orm.deferred`, the :paramref:`_orm.deferred.group`
parameter may be used.

The example below defines a mapping with a ``photos`` deferred group. When
an attribute within the group ``.photo1``, ``.photo2``, ``.photo3``
is accessed on an instance of ``Book``, all three columns will be loaded in one SELECT
statement. The ``.excerpt`` column however will only be loaded when it
is directly accessed::

    from sqlalchemy import Text
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.orm import Mapped
    from sqlalchemy.orm import mapped_column

    class Base(DeclarativeBase):
        pass

    class Book(Base):
        __tablename__ = 'book'

        book_id: Mapped[int] = mapped_column(primary_key=True)
        title: Mapped[str]
        summary: Mapped[str]
        excerpt: Mapped[str] = mapped_column(Text, deferred=True)
        photo1: Mapped[bytes] = mapped_column(deferred_group="photos")
        photo2: Mapped[bytes] = mapped_column(deferred_group="photos")
        photo3: Mapped[bytes] = mapped_column(deferred_group="photos")


.. _deferred_options:

Deferred Column Loader Query Options
------------------------------------
At query time, the :func:`_orm.defer`, :func:`_orm.undefer` and
:func:`_orm.undefer_group` loader options may be used to further control the
"deferral behavior" of mapped columns.

Columns can be marked as "deferred" or reset to "undeferred" at query time
using options which are passed to the :meth:`_sql.Select.options` method; the most
basic query options are :func:`_orm.defer` and
:func:`_orm.undefer`::

    from sqlalchemy.orm import defer
    from sqlalchemy.orm import undefer
    from sqlalchemy import select

    stmt = select(Book)
    stmt = stmt.options(defer(Book.summary), undefer(Book.excerpt))
    book_objs = session.scalars(stmt).all()


Above, the "summary" column will not load until accessed, and the "excerpt"
column will load immediately even if it was mapped as a "deferred" column.

:func:`_orm.deferred` attributes which are marked with a "group" can be undeferred
using :func:`_orm.undefer_group`, sending in the group name::

    from sqlalchemy.orm import undefer_group
    from sqlalchemy import select

    stmt = select(Book)
    stmt = stmt.options(undefer_group('photos'))
    book_objs = session.scalars(stmt).all()


.. _deferred_loading_w_multiple:

Deferred Loading across Multiple Entities
-----------------------------------------

Column deferral may also be used for a statement that loads multiple types of
entities at once, by referring to the appropriate class bound attribute
within the :func:`_orm.defer` function.  Suppose ``Book`` has a
relationship ``Book.author`` to a related class ``Author``, we could write
a query as follows which will defer the ``Author.bio`` column::

    from sqlalchemy.orm import defer
    from sqlalchemy import select

    stmt = select(Book, Author).join(Book.author)
    stmt = stmt.options(defer(Author.bio))

    book_author_objs = session.execute(stmt).all()


Column deferral options may also indicate that they take place along various
relationship paths, which are themselves often :ref:`eagerly loaded
<loading_toplevel>` with loader options.  All relationship-bound loader options
support chaining  onto additional loader options, which include loading for
further levels of relationships, as well as onto column-oriented attributes at
that path. Such as, to load ``Author`` instances, then joined-eager-load the
``Author.books`` collection for each author, then apply deferral options to
column-oriented attributes onto each ``Book`` entity from that relationship,
the :func:`_orm.joinedload` loader option can be combined with the :func:`.load_only`
option (described later in this section) to defer all ``Book`` columns except
those explicitly specified::

    from sqlalchemy.orm import joinedload
    from sqlalchemy import select

    stmt = select(Author)
    stmt = stmt.options(
        joinedload(Author.books).load_only(Book.summary, Book.excerpt)
    )

    author_objs = session.scalars(stmt).all()

Option structures as above can also be organized in more complex ways, such
as hierarchically using the :meth:`_orm.Load.options`
method, which allows multiple sub-options to be chained to a common parent
option at once.   The example below illustrates a more complex structure::

    from sqlalchemy.orm import defer
    from sqlalchemy.orm import joinedload
    from sqlalchemy.orm import load_only
    from sqlalchemy import select

    stmt = select(Author)
    stmt = stmt.options(
        joinedload(Author.book).options(
            load_only(Book.summary, Book.excerpt),
            joinedload(Book.citations).options(
                joinedload(Citation.author),
                defer(Citation.fulltext)
            )
        )
    )
    author_objs = session.scalars(stmt).all()


Another way to apply options to a path is to use the :func:`_orm.defaultload`
function.   This function is used to indicate a particular path within a loader
option structure without actually setting any options at that level, so that further
sub-options may be applied.  The :func:`_orm.defaultload` function can be used
to create the same structure as we did above using :meth:`_orm.Load.options` as::

    from sqlalchemy import select
    from sqlalchemy.orm import defaultload

    stmt = select(Author)
    stmt = stmt.options(
        joinedload(Author.book).load_only(Book.summary, Book.excerpt),
        defaultload(Author.book).joinedload(Book.citations).joinedload(Citation.author),
        defaultload(Author.book).defaultload(Book.citations).defer(Citation.fulltext)
    )

    author_objs = session.scalars(stmt).all()

.. seealso::

    :ref:`relationship_loader_options` - targeted towards relationship loading

Load Only and Wildcard Options
------------------------------

The ORM loader option system supports the concept of "wildcard" loader options,
in which a loader option can be passed an asterisk ``"*"`` to indicate that
a particular option should apply to all applicable attributes of a mapped
class.   Such as, if we wanted to load the ``Book`` class but only
the "summary" and "excerpt" columns, we could say::

    from sqlalchemy.orm import defer
    from sqlalchemy.orm import undefer
    from sqlalchemy import select

    stmt = select(Book).options(
        defer('*'), undefer(Book.summary), undefer(Book.excerpt))

    book_objs = session.scalars(stmt).all()

Above, the :func:`.defer` option is applied using a wildcard to all column
attributes on the ``Book`` class.   Then, the :func:`.undefer` option is used
against the "summary" and "excerpt" fields so that they are the  only columns
loaded up front. A query for the above entity will include only the "summary"
and "excerpt" fields in the SELECT, along with the primary key columns which
are always used by the ORM.

A similar function is available with less verbosity by using the
:func:`_orm.load_only` option.  This is a so-called **exclusionary** option
which will apply deferred behavior to all column attributes except those
that are named::

    from sqlalchemy.orm import load_only
    from sqlalchemy import select

    stmt = select(Book).options(load_only(Book.summary, Book.excerpt))

    book_objs = session.scalars(stmt).all()

Wildcard and Exclusionary Options with Multiple-Entity Queries
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Wildcard options and exclusionary options such as :func:`.load_only` may
only be applied to a single entity at a time within a statement.
To suit the less common case where a statement is returning multiple
primary entities at once, a special calling style may be required in order
to apply a wildcard or exclusionary option to a specific entity, which is to use the
:class:`_orm.Load` object to indicate the starting entity for a deferral option.
Such as, if we were loading ``Book`` and ``Author`` at once, the ORM
will raise an informative error if we try to apply :func:`.load_only` to
both at once.  Instead, we may use :class:`_orm.Load` to apply the option
to either or both of ``Book`` and ``Author`` individually::

    from sqlalchemy.orm import Load

    stmt = select(Book, Author).join(Book.author)
    stmt = stmt.options(
                Load(Book).load_only(Book.summary, Book.excerpt)
            )
    book_author_objs = session.execute(stmt).all()

Above, :class:`_orm.Load` is used in conjunction with the exclusionary option
:func:`.load_only` so that the deferral of all other columns only takes
place for the ``Book`` class and not the ``Author`` class.   Again,
the ORM should raise an informative error message when
the above calling style is actually required that describes those cases
where explicit use of :class:`_orm.Load` is needed.

.. _deferred_raiseload:

Raiseload for Deferred Columns
------------------------------

.. versionadded:: 1.4

The :func:`.deferred` loader option and the corresponding loader strategy also
support the concept of "raiseload", which is a loader strategy that will raise
:class:`.InvalidRequestError` if the attribute is accessed such that it would
need to emit a SQL query in order to be loaded.   This behavior is the
column-based equivalent of the :func:`_orm.raiseload` feature for relationship
loading, discussed at :ref:`prevent_lazy_with_raiseload`.    Using the
:paramref:`_orm.defer.raiseload` parameter on the :func:`_orm.defer` option,
an exception is raised if the attribute is accessed::

    book = session.scalar(
      select(Book).options(defer(Book.summary, raiseload=True)).limit(1)
    )

    # would raise an exception
    book.summary

Deferred "raiseload" can be configured at the mapper level via
:paramref:`.orm.deferred.raiseload` on either :func:`_orm.mapped_column`
or in :func:`.deferred`, so that an explicit
:func:`.undefer` is required in order for the attribute to be usable.
Below is a :ref:`Declarative table <orm_declarative_table>` configuration example::


    from sqlalchemy import Text
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.orm import Mapped
    from sqlalchemy.orm import mapped_column

    class Base(DeclarativeBase):
        pass

    class Book(Base):
        __tablename__ = 'book'

        book_id: Mapped[int] = mapped_column(primary_key=True)
        title: Mapped[str]
        summary: Mapped[str] = mapped_column(raiseload=True)
        excerpt: Mapped[str] = mapped_column(Text, raiseload=True)

Alternatively, the example below illustrates the same mapping using a
:ref:`Imperative table <orm_imperative_table_configuration>` configuration::

    from sqlalchemy import Column, Integer, LargeBinary, String, Table, Text
    from sqlalchemy.orm import DeclarativeBase
    from sqlalchemy.orm import deferred


    class Base(DeclarativeBase):
        pass


    book = Table(
        "book",
        Base.metadata,
        Column("book_id", Integer, primary_key=True),
        Column("title", String),
        Column("summary", String),
        Column("excerpt", Text),
    )


    class Book(Base):
        __table__ = book

        summary = deferred(book.c.summary, raiseload=True)
        excerpt = deferred(book.c.excerpt, raiseload=True)

With both mappings, if we wish to have either or both of ``.excerpt``
or ``.summary`` available on an object when loaded, we make use of the
:func:`_orm.undefer` loader option::

    book_w_excerpt = session.scalars(
      select(Book).options(undefer(Book.excerpt)).where(Book.id == 12)
    ).first()

The :func:`_orm.undefer` option will populate the ``.excerpt`` attribute
above, even if the ``Book`` object were already loaded, assuming the
``.excerpt`` field was not populated by some other means previously.


Column Deferral API
-------------------

.. autofunction:: defer

.. autofunction:: deferred

.. autofunction:: query_expression

.. autofunction:: load_only

.. autofunction:: undefer

.. autofunction:: undefer_group

.. autofunction:: with_expression

.. _bundles:

Column Bundles
==============

The :class:`_orm.Bundle` may be used to query for groups of columns under one
namespace.

The bundle allows columns to be grouped together::

    from sqlalchemy.orm import Bundle
    from sqlalchemy import select

    bn = Bundle('mybundle', MyClass.data1, MyClass.data2)
    for row in session.execute(select(bn).where(bn.c.title == "d1")):
        print(row.mybundle.data1, row.mybundle.data2)

The bundle can be subclassed to provide custom behaviors when results
are fetched.  The method :meth:`.Bundle.create_row_processor` is given
the statement object and a set of "row processor" functions at query execution
time; these processor functions when given a result row will return the
individual attribute value, which can then be adapted into any kind of
return data structure.  Below illustrates replacing the usual :class:`.Row`
return structure with a straight Python dictionary::

    from sqlalchemy.orm import Bundle

    class DictBundle(Bundle):
        def create_row_processor(self, query, procs, labels):
            """Override create_row_processor to return values as dictionaries"""
            def proc(row):
                return dict(
                            zip(labels, (proc(row) for proc in procs))
                        )
            return proc

.. note::

    The :class:`_orm.Bundle` construct only applies to column expressions.
    It does not apply to ORM attributes mapped using :func:`_orm.relationship`.

.. versionchanged:: 1.0

   The ``proc()`` callable passed to the ``create_row_processor()``
   method of custom :class:`.Bundle` classes now accepts only a single
   "row" argument.

A result from the above bundle will return dictionary values::

    bn = DictBundle('mybundle', MyClass.data1, MyClass.data2)
    for row in session.execute(select(bn)).where(bn.c.data1 == 'd1'):
        print(row.mybundle['data1'], row.mybundle['data2'])

The :class:`.Bundle` construct is also integrated into the behavior
of :func:`.composite`, where it is used to return composite attributes as objects
when queried as individual attributes.

