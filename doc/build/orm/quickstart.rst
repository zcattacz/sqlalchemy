.. _orm_quickstart:


ORM Quick Start
===============

For new users who want to quickly see what basic ORM use looks like, here's an
abbreviated form of the mappings and examples used in the
:ref:`unified_tutorial`. The code here is fully runnable from a clean command
line.

As the descriptions in this section are intentionally **very short**, please
proceed to the full :ref:`unified_tutorial` for a much more in-depth
description of each of the concepts being illustrated here.

.. versionchanged:: 2.0  The ORM Quickstart is updated for the latest
    :pep:`484`-aware features using new constructs including
    :func:`_orm.mapped_column`.   At the moment, the rest of the documentation
    may not be yet updated.   Features such as a new dataclass-native style
    of mapping are also not documented yet.

Declare Models
---------------

Here, we define module-level constructs that will form the structures
which we will be querying from the database.  This structure, known as a
:ref:`Declarative Mapping <orm_declarative_mapping>`, defines at once both a
Python object model, as well as :term:`database metadata` that describes
real SQL tables that exist, or will exist, in a particular database::

    >>> from typing import Optional
    >>> from sqlalchemy import ForeignKey
    >>> from sqlalchemy import String
    >>> from sqlalchemy.orm import DeclarativeBase
    >>> from sqlalchemy.orm import Mapped
    >>> from sqlalchemy.orm import mapped_column
    >>> from sqlalchemy.orm import relationship

    >>> class Base(DeclarativeBase):
    ...     pass

    >>> class User(Base):
    ...     __tablename__ = "user_account"
    ...
    ...     id: Mapped[int] = mapped_column(primary_key=True)
    ...     name: Mapped[str] = mapped_column(String(30))
    ...     fullname: Mapped[Optional[str]]
    ...
    ...     addresses: Mapped[list["Address"]] = relationship(
    ...         back_populates="user", cascade="all, delete-orphan"
    ...     )
    ...
    ...     def __repr__(self) -> str:
    ...         return f"User(id={self.id!r}, name={self.name!r}, fullname={self.fullname!r})"

    >>> class Address(Base):
    ...     __tablename__ = "address"
    ...
    ...     id: Mapped[int] = mapped_column(primary_key=True)
    ...     email_address: Mapped[str]
    ...     user_id: Mapped[int] = mapped_column(ForeignKey("user_account.id"))
    ...
    ...     user: Mapped["User"] = relationship(back_populates="addresses")
    ...
    ...     def __repr__(self) -> str:
    ...         return f"Address(id={self.id!r}, email_address={self.email_address!r})"

Above, new ORM mapped classes are declared as part of a common base, which is
configured as a user-defined class that inherits from the special
:class:`_orm.DeclarativeBase` class. Then, the declarative mapping makes use of
both the :class:`_orm.Mapped` type annotation construct to indicate class
attributes that are mapped, and then makes use of the
:func:`_orm.mapped_column` and :func:`_orm.relationship` constructs to further
qualify the specifics of how these attributes should be mapped where necessary.
The :func:`_orm.mapped_column` construct indicates the presence of a relational
database column, which is also implied by default when :class:`_orm.Mapped` is
annotated without a right-hand side value. The :func:`_orm.relationship`
construct, by contrast, defines linkages between two :term:`mapped` classes,
``User`` and ``Address`` above.

Most arguments accepted by :func:`_orm.mapped_column` align with the underlying
construct that represents a database table column, which is the
:class:`_schema.Column` object. The schema contains necessary elements such as
primary key constraints set up using the
:paramref:`_orm.mapped_column.primary_key` parameter, a
:term:`foreign key constraint` configured using the :class:`_schema.ForeignKey`
construct, and datatypes for columns including :class:`_types.Integer`, which
is implied by the use of the Python ``int`` datatype, and
:class:`_types.String`, which is implied by the use of the Python ``str``
datatype. The "nullability" of columns by default is inferred by whether or not
the left-hand :class:`_orm.Mapped` datatype is stated as ``Optional[<type>]``
or not.

In all cases, parameters passed to :func:`_orm.mapped_column`, such as specific
datatype specifications such as ``String(30)``, or use of the the boolean parameter
:paramref:`_orm.mapped_column.nullable`, will supersede the annotation-implied
configuration.

While the above classes include an explicitly written ``__repr__()`` method,
which is used here to illustrate usage of the classes, there is also an
option for methods such as ``__repr__()``, ``__eq__()`` and others to be
generated automatically using Python dataclasses.  More on dataclass mapping
at :ref:`orm_declarative_native_dataclasses`.

More on table metadata and an intro to ORM declared mapping is in the
Tutorial at :ref:`tutorial_working_with_metadata`.

Create an Engine
------------------


The :class:`_engine.Engine` is a **factory** that can create new
database connections for us, which also holds onto connections inside
of a :ref:`Connection Pool <pooling_toplevel>` for fast reuse.  For learning
purposes, we normally use a :ref:`SQLite <sqlite_toplevel>` memory-only database
for convenience::

    >>> from sqlalchemy import create_engine
    >>> engine = create_engine("sqlite://", echo=True)

.. tip::

    The ``echo=True`` parameter indicates that SQL emitted by connections will
    be logged to standard out.

A full intro to the :class:`_engine.Engine` starts at :ref:`tutorial_engine`.

Emit CREATE TABLE DDL
----------------------


Using our table metadata and our engine, we can generate our schema at once
in our target SQLite database, using a method called :meth:`_schema.MetaData.create_all`:

.. sourcecode:: pycon+sql

    >>> Base.metadata.create_all(engine)
    {opensql}BEGIN (implicit)
    PRAGMA main.table_...info("user_account")
    ...
    PRAGMA main.table_...info("address")
    ...
    CREATE TABLE user_account (
        id INTEGER NOT NULL,
        name VARCHAR(30) NOT NULL,
        fullname VARCHAR,
        PRIMARY KEY (id)
    )
    ...
    CREATE TABLE address (
        id INTEGER NOT NULL,
        email_address VARCHAR NOT NULL,
        user_id INTEGER NOT NULL,
        PRIMARY KEY (id),
        FOREIGN KEY(user_id) REFERENCES user_account (id)
    )
    ...
    COMMIT

A lot just happened from that bit of Python code we wrote.  For a complete
overview of what's going on on with Table metadata, proceed in the
Tutorial at :ref:`tutorial_working_with_metadata`.

Create Objects and Persist
---------------------------

We are now ready to insert data in the database.  We accomplish this by
creating instances of ``User`` and ``Address`` objects, which have
an ``__init__()`` method already as established automatically by the
declarative mapping process.  We then pass them
to the database using an object called a :ref:`Session <tutorial_executing_orm_session>`,
which makes use of the :class:`_engine.Engine` to interact with the
database.  The :meth:`_orm.Session.add_all` method is used here to add
multiple objects at once, and the :meth:`_orm.Session.commit` method
will be used to :ref:`flush <session_flushing>` any pending changes to the
database and then :ref:`commit <session_committing>` the current database
transaction, which is always in progress whenever the :class:`_orm.Session`
is used:

.. sourcecode:: pycon+sql

    >>> from sqlalchemy.orm import Session

    >>> with Session(engine) as session:
    ...
    ...     spongebob = User(
    ...         name="spongebob",
    ...         fullname="Spongebob Squarepants",
    ...         addresses=[Address(email_address="spongebob@sqlalchemy.org")],
    ...     )
    ...     sandy = User(
    ...         name="sandy",
    ...         fullname="Sandy Cheeks",
    ...         addresses=[
    ...             Address(email_address="sandy@sqlalchemy.org"),
    ...             Address(email_address="sandy@squirrelpower.org"),
    ...         ],
    ...     )
    ...     patrick = User(name="patrick", fullname="Patrick Star")
    ...
    ...     session.add_all([spongebob, sandy, patrick])
    ...
    ...     session.commit()
    {opensql}BEGIN (implicit)
    INSERT INTO user_account (name, fullname) VALUES (?, ?)
    [...] ('spongebob', 'Spongebob Squarepants')
    INSERT INTO user_account (name, fullname) VALUES (?, ?)
    [...] ('sandy', 'Sandy Cheeks')
    INSERT INTO user_account (name, fullname) VALUES (?, ?)
    [...] ('patrick', 'Patrick Star')
    INSERT INTO address (email_address, user_id) VALUES (?, ?)
    [...] ('spongebob@sqlalchemy.org', 1)
    INSERT INTO address (email_address, user_id) VALUES (?, ?)
    [...] ('sandy@sqlalchemy.org', 2)
    INSERT INTO address (email_address, user_id) VALUES (?, ?)
    [...] ('sandy@squirrelpower.org', 2)
    COMMIT


.. tip::

    It's recommended that the :class:`_orm.Session` be used in context
    manager style as above, that is, using the Python ``with:`` statement.
    The :class:`_orm.Session` object represents active database resources
    so it's good to make sure it's closed out when a series of operations
    are completed.  In the next section, we'll keep a :class:`_orm.Session`
    opened just for illustration purposes.

Basics on creating a :class:`_orm.Session` are at
:ref:`tutorial_executing_orm_session` and more at :ref:`session_basics`.

Then, some varieties of basic persistence operations are introduced
at :ref:`tutorial_inserting_orm`.

Simple SELECT
--------------

With some rows in the database, here's the simplest form of emitting a SELECT
statement to load some objects. To create SELECT statements, we use the
:func:`_sql.select` function to create a new :class:`_sql.Select` object, which
we then invoke using a :class:`_orm.Session`. The method that is often useful
when querying for ORM objects is the :meth:`_orm.Session.scalars` method, which
will return a :class:`_result.ScalarResult` object that will iterate through
the ORM objects we've selected:

.. sourcecode:: pycon+sql

    >>> from sqlalchemy import select

    >>> session = Session(engine)

    >>> stmt = select(User).where(User.name.in_(["spongebob", "sandy"]))

    >>> for user in session.scalars(stmt):
    ...     print(user)
    {opensql}BEGIN (implicit)
    SELECT user_account.id, user_account.name, user_account.fullname
    FROM user_account
    WHERE user_account.name IN (?, ?)
    [...] ('spongebob', 'sandy'){stop}
    User(id=1, name='spongebob', fullname='Spongebob Squarepants')
    User(id=2, name='sandy', fullname='Sandy Cheeks')


The above query also made use of the :meth:`_sql.Select.where` method
to add WHERE criteria, and also used the :meth:`_sql.ColumnOperators.in_`
method that's part of all SQLAlchemy column-like constructs to use the
SQL IN operator.

More detail on how to select objects and individual columns is at
:ref:`tutorial_selecting_orm_entities`.

SELECT with JOIN
-----------------

It's very common to query amongst multiple tables at once, and in SQL
the JOIN keyword is the primary way this happens.   The :class:`_sql.Select`
construct creates joins using the :meth:`_sql.Select.join` method:

.. sourcecode:: pycon+sql

    >>> stmt = (
    ...  select(Address)
    ...  .join(Address.user)
    ...  .where(User.name == "sandy")
    ...  .where(Address.email_address == "sandy@sqlalchemy.org")
    ... )
    >>> sandy_address = session.scalars(stmt).one()
    {opensql}SELECT address.id, address.email_address, address.user_id
    FROM address JOIN user_account ON user_account.id = address.user_id
    WHERE user_account.name = ? AND address.email_address = ?
    [...] ('sandy', 'sandy@sqlalchemy.org')
    {stop}
    >>> sandy_address
    Address(id=2, email_address='sandy@sqlalchemy.org')

The above query illustrates multiple WHERE criteria which are automatically
chained together using AND, as well as how to use SQLAlchemy column-like
objects to create "equality" comparisons, which uses the overridden Python
method :meth:`_sql.ColumnOperators.__eq__` to produce a SQL criteria object.

Some more background on the concepts above are at
:ref:`tutorial_select_where_clause` and :ref:`tutorial_select_join`.

Make Changes
------------

The :class:`_orm.Session` object, in conjunction with our ORM-mapped classes
``User`` and ``Address``, automatically track changes to the objects as they
are made, which result in SQL statements that will be emitted the next
time the :class:`_orm.Session` flushes.   Below, we change one email
address associated with "sandy", and also add a new email address to
"patrick", after emitting a SELECT to retrieve the row for "patrick":

.. sourcecode:: pycon+sql

    >>> stmt = select(User).where(User.name == "patrick")
    >>> patrick = session.scalars(stmt).one()
    {opensql}SELECT user_account.id, user_account.name, user_account.fullname
    FROM user_account
    WHERE user_account.name = ?
    [...] ('patrick',)
    {stop}

    >>> patrick.addresses.append(
    ...     Address(email_address="patrickstar@sqlalchemy.org")
    ... )
    {opensql}SELECT address.id AS address_id, address.email_address AS address_email_address, address.user_id AS address_user_id
    FROM address
    WHERE ? = address.user_id
    [...] (3,){stop}

    >>> sandy_address.email_address = "sandy_cheeks@sqlalchemy.org"

    >>> session.commit()
    {opensql}UPDATE address SET email_address=? WHERE address.id = ?
    [...] ('sandy_cheeks@sqlalchemy.org', 2)
    INSERT INTO address (email_address, user_id) VALUES (?, ?)
    [...] ('patrickstar@sqlalchemy.org', 3)
    COMMIT
    {stop}

Notice when we accessed ``patrick.addresses``, a SELECT was emitted.  This is
called a :term:`lazy load`.   Background on different ways to access related
items using more or less SQL is introduced at :ref:`tutorial_orm_loader_strategies`.

A detailed walkthrough on ORM data manipulation starts at
:ref:`tutorial_orm_data_manipulation`.

Some Deletes
------------

All things must come to an end, as is the case for some of our database
rows - here's a quick demonstration of two different forms of deletion, both
of which are important based on the specific use case.

First we will remove one of the ``Address`` objects from the "sandy" user.
When the :class:`_orm.Session` next flushes, this will result in the
row being deleted.   This behavior is something that we configured in our
mapping called the :ref:`delete cascade <cascade_delete>`.  We can get a handle to the ``sandy``
object by primary key using :meth:`_orm.Session.get`, then work with the object:

.. sourcecode:: pycon+sql

    >>> sandy = session.get(User, 2)
    {opensql}BEGIN (implicit)
    SELECT user_account.id AS user_account_id, user_account.name AS user_account_name, user_account.fullname AS user_account_fullname
    FROM user_account
    WHERE user_account.id = ?
    [...] (2,){stop}

    >>> sandy.addresses.remove(sandy_address)
    {opensql}SELECT address.id AS address_id, address.email_address AS address_email_address, address.user_id AS address_user_id
    FROM address
    WHERE ? = address.user_id
    [...] (2,)

The last SELECT above was the :term:`lazy load` operation proceeding so that
the ``sandy.addresses`` collection could be loaded, so that we could remove the
``sandy_address`` member.  There are other ways to go about this series
of operations that won't emit as much SQL.

We can choose to emit the DELETE SQL for what's set to be changed so far, without
committing the transaction, using the
:meth:`_orm.Session.flush` method:

.. sourcecode:: pycon+sql

    >>> session.flush()
    {opensql}DELETE FROM address WHERE address.id = ?
    [...] (2,)

Next, we will delete the "patrick" user entirely.  For a top-level delete of
an object by itself, we use the :meth:`_orm.Session.delete` method; this
method doesn't actually perform the deletion, but sets up the object
to be deleted on the next flush.  The
operation will also :term:`cascade` to related objects based on the cascade
options that we configured, in this case, onto the related ``Address`` objects:

.. sourcecode:: pycon+sql

    >>> session.delete(patrick)
    {opensql}SELECT user_account.id AS user_account_id, user_account.name AS user_account_name, user_account.fullname AS user_account_fullname
    FROM user_account
    WHERE user_account.id = ?
    [...] (3,)
    SELECT address.id AS address_id, address.email_address AS address_email_address, address.user_id AS address_user_id
    FROM address
    WHERE ? = address.user_id
    [...] (3,)

The :meth:`_orm.Session.delete` method in this particular case emitted two
SELECT statements, even though it didn't emit a DELETE, which might seem surprising.
This is because when the method went to inspect the object, it turns out the
``patrick`` object was :term:`expired`, which happened when we last called upon
:meth:`_orm.Session.commit`, and the SQL emitted was to re-load the rows
from the new transaction.   This expiration is optional, and in normal
use we will often be turning it off for situations where it doesn't apply well.

To illustrate the rows being deleted, here's the commit:

.. sourcecode:: pycon+sql

    >>> session.commit()
    {opensql}DELETE FROM address WHERE address.id = ?
    [...] (4,)
    DELETE FROM user_account WHERE user_account.id = ?
    [...] (3,)
    COMMIT
    {stop}

The Tutorial discusses ORM deletion at :ref:`tutorial_orm_deleting`.
Background on object expiration is at :ref:`session_expiring`; cascades
are discussed in depth at :ref:`unitofwork_cascades`.

Learn the above concepts in depth
---------------------------------

For a new user, the above sections were likely a whirlwind tour.   There's a
lot of important concepts in each step above that weren't covered.   With a
quick overview of what things look like, it's recommended to work through
the :ref:`unified_tutorial` to gain a solid working knowledge of what's
really going on above.  Good luck!





