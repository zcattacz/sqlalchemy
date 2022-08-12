# coding: utf-8


from sqlalchemy import CHAR
from sqlalchemy import Double
from sqlalchemy import exc
from sqlalchemy import FLOAT
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import ForeignKeyConstraint
from sqlalchemy import func
from sqlalchemy import Identity
from sqlalchemy import Index
from sqlalchemy import inspect
from sqlalchemy import INTEGER
from sqlalchemy import Integer
from sqlalchemy import MetaData
from sqlalchemy import NCHAR
from sqlalchemy import Numeric
from sqlalchemy import PrimaryKeyConstraint
from sqlalchemy import select
from sqlalchemy import String
from sqlalchemy import testing
from sqlalchemy import text
from sqlalchemy import Unicode
from sqlalchemy import UniqueConstraint
from sqlalchemy.dialects import oracle
from sqlalchemy.dialects.oracle.base import BINARY_DOUBLE
from sqlalchemy.dialects.oracle.base import BINARY_FLOAT
from sqlalchemy.dialects.oracle.base import DOUBLE_PRECISION
from sqlalchemy.dialects.oracle.base import NUMBER
from sqlalchemy.dialects.oracle.base import REAL
from sqlalchemy.dialects.oracle.types import NVARCHAR2
from sqlalchemy.dialects.oracle.types import VARCHAR2
from sqlalchemy.engine import ObjectKind
from sqlalchemy.sql.sqltypes import NVARCHAR
from sqlalchemy.sql.sqltypes import VARCHAR
from sqlalchemy.testing import assert_warns
from sqlalchemy.testing import AssertsCompiledSQL
from sqlalchemy.testing import config
from sqlalchemy.testing import eq_
from sqlalchemy.testing import expect_raises
from sqlalchemy.testing import fixtures
from sqlalchemy.testing import is_
from sqlalchemy.testing import is_true
from sqlalchemy.testing.engines import testing_engine
from sqlalchemy.testing.schema import Column
from sqlalchemy.testing.schema import eq_compile_type
from sqlalchemy.testing.schema import Table


class MultiSchemaTest(fixtures.TestBase, AssertsCompiledSQL):
    __only_on__ = "oracle"
    __backend__ = True

    @classmethod
    def setup_test_class(cls):
        # currently assuming full DBA privs for the user.
        # don't really know how else to go here unless
        # we connect as the other user.

        with testing.db.begin() as conn:
            for stmt in (
                """
    create table %(test_schema)s.parent(
        id integer primary key,
        data varchar2(50)
    );

    COMMENT ON TABLE %(test_schema)s.parent IS 'my table comment';

    create table %(test_schema)s.child(
        id integer primary key,
        data varchar2(50),
        parent_id integer references %(test_schema)s.parent(id)
    );

    create table local_table(
        id integer primary key,
        data varchar2(50)
    );

    create synonym %(test_schema)s.ptable for %(test_schema)s.parent;
    create synonym %(test_schema)s.ctable for %(test_schema)s.child;

    create synonym %(test_schema)s_pt for %(test_schema)s.parent;

    create synonym %(test_schema)s.local_table for local_table;

    -- can't make a ref from local schema to the
    -- remote schema's table without this,
    -- *and* can't give yourself a grant !
    -- so we give it to public.  ideas welcome.
    grant references on %(test_schema)s.parent to public;
    grant references on %(test_schema)s.child to public;
    """
                % {"test_schema": testing.config.test_schema}
            ).split(";"):
                if stmt.strip():
                    conn.exec_driver_sql(stmt)

    @classmethod
    def teardown_test_class(cls):
        with testing.db.begin() as conn:
            for stmt in (
                """
    drop table %(test_schema)s.child;
    drop table %(test_schema)s.parent;
    drop table local_table;
    drop synonym %(test_schema)s.ctable;
    drop synonym %(test_schema)s.ptable;
    drop synonym %(test_schema)s_pt;
    drop synonym %(test_schema)s.local_table;

    """
                % {"test_schema": testing.config.test_schema}
            ).split(";"):
                if stmt.strip():
                    conn.exec_driver_sql(stmt)

    def test_create_same_names_explicit_schema(self, metadata, connection):
        schema = testing.db.dialect.default_schema_name
        meta = metadata
        parent = Table(
            "parent",
            meta,
            Column("pid", Integer, primary_key=True),
            schema=schema,
        )
        child = Table(
            "child",
            meta,
            Column("cid", Integer, primary_key=True),
            Column("pid", Integer, ForeignKey("%s.parent.pid" % schema)),
            schema=schema,
        )
        meta.create_all(connection)
        connection.execute(parent.insert(), {"pid": 1})
        connection.execute(child.insert(), {"cid": 1, "pid": 1})
        eq_(connection.execute(child.select()).fetchall(), [(1, 1)])

    def test_reflect_alt_table_owner_local_synonym(self):
        meta = MetaData()
        parent = Table(
            "%s_pt" % testing.config.test_schema,
            meta,
            autoload_with=testing.db,
            oracle_resolve_synonyms=True,
        )
        self.assert_compile(
            parent.select(),
            "SELECT %(test_schema)s_pt.id, "
            "%(test_schema)s_pt.data FROM %(test_schema)s_pt"
            % {"test_schema": testing.config.test_schema},
        )

    def test_reflect_alt_synonym_owner_local_table(self):
        meta = MetaData()
        parent = Table(
            "local_table",
            meta,
            autoload_with=testing.db,
            oracle_resolve_synonyms=True,
            schema=testing.config.test_schema,
        )
        self.assert_compile(
            parent.select(),
            "SELECT %(test_schema)s.local_table.id, "
            "%(test_schema)s.local_table.data "
            "FROM %(test_schema)s.local_table"
            % {"test_schema": testing.config.test_schema},
        )

    def test_create_same_names_implicit_schema(self, metadata, connection):
        meta = metadata
        parent = Table(
            "parent", meta, Column("pid", Integer, primary_key=True)
        )
        child = Table(
            "child",
            meta,
            Column("cid", Integer, primary_key=True),
            Column("pid", Integer, ForeignKey("parent.pid")),
        )
        meta.create_all(connection)

        connection.execute(parent.insert(), {"pid": 1})
        connection.execute(child.insert(), {"cid": 1, "pid": 1})
        eq_(connection.execute(child.select()).fetchall(), [(1, 1)])

    def test_reflect_alt_owner_explicit(self):
        meta = MetaData()
        parent = Table(
            "parent",
            meta,
            autoload_with=testing.db,
            schema=testing.config.test_schema,
        )
        child = Table(
            "child",
            meta,
            autoload_with=testing.db,
            schema=testing.config.test_schema,
        )

        self.assert_compile(
            parent.join(child),
            "%(test_schema)s.parent JOIN %(test_schema)s.child ON "
            "%(test_schema)s.parent.id = %(test_schema)s.child.parent_id"
            % {"test_schema": testing.config.test_schema},
        )
        with testing.db.connect() as conn:
            conn.execute(
                select(parent, child).select_from(parent.join(child))
            ).fetchall()

        # check table comment (#5146)
        eq_(parent.comment, "my table comment")

    def test_reflect_table_comment(self, metadata, connection):
        local_parent = Table(
            "parent",
            metadata,
            Column("q", Integer),
            comment="my local comment",
        )

        local_parent.create(connection)

        insp = inspect(connection)
        eq_(
            insp.get_table_comment(
                "parent", schema=testing.config.test_schema
            ),
            {"text": "my table comment"},
        )
        eq_(
            insp.get_table_comment(
                "parent",
            ),
            {"text": "my local comment"},
        )
        eq_(
            insp.get_table_comment(
                "parent", schema=connection.dialect.default_schema_name
            ),
            {"text": "my local comment"},
        )

    def test_reflect_local_to_remote(self, connection):
        connection.exec_driver_sql(
            "CREATE TABLE localtable (id INTEGER "
            "PRIMARY KEY, parent_id INTEGER REFERENCES "
            "%(test_schema)s.parent(id))"
            % {"test_schema": testing.config.test_schema},
        )
        try:
            meta = MetaData()
            lcl = Table("localtable", meta, autoload_with=testing.db)
            parent = meta.tables["%s.parent" % testing.config.test_schema]
            self.assert_compile(
                parent.join(lcl),
                "%(test_schema)s.parent JOIN localtable ON "
                "%(test_schema)s.parent.id = "
                "localtable.parent_id"
                % {"test_schema": testing.config.test_schema},
            )
        finally:
            connection.exec_driver_sql("DROP TABLE localtable")

    def test_reflect_alt_owner_implicit(self):
        meta = MetaData()
        parent = Table(
            "parent",
            meta,
            autoload_with=testing.db,
            schema=testing.config.test_schema,
        )
        child = Table(
            "child",
            meta,
            autoload_with=testing.db,
            schema=testing.config.test_schema,
        )
        self.assert_compile(
            parent.join(child),
            "%(test_schema)s.parent JOIN %(test_schema)s.child "
            "ON %(test_schema)s.parent.id = "
            "%(test_schema)s.child.parent_id"
            % {"test_schema": testing.config.test_schema},
        )
        with testing.db.connect() as conn:
            conn.execute(
                select(parent, child).select_from(parent.join(child))
            ).fetchall()

    def test_reflect_alt_owner_synonyms(self, connection):
        connection.exec_driver_sql(
            "CREATE TABLE localtable (id INTEGER "
            "PRIMARY KEY, parent_id INTEGER REFERENCES "
            "%s.ptable(id))" % testing.config.test_schema,
        )
        try:
            meta = MetaData()
            lcl = Table(
                "localtable",
                meta,
                autoload_with=connection,
                oracle_resolve_synonyms=True,
            )
            parent = meta.tables["%s.ptable" % testing.config.test_schema]
            self.assert_compile(
                parent.join(lcl),
                "%(test_schema)s.ptable JOIN localtable ON "
                "%(test_schema)s.ptable.id = "
                "localtable.parent_id"
                % {"test_schema": testing.config.test_schema},
            )
            connection.execute(
                select(parent, lcl).select_from(parent.join(lcl))
            ).fetchall()
        finally:
            connection.exec_driver_sql("DROP TABLE localtable")

    def test_reflect_remote_synonyms(self):
        meta = MetaData()
        parent = Table(
            "ptable",
            meta,
            autoload_with=testing.db,
            schema=testing.config.test_schema,
            oracle_resolve_synonyms=True,
        )
        child = Table(
            "ctable",
            meta,
            autoload_with=testing.db,
            schema=testing.config.test_schema,
            oracle_resolve_synonyms=True,
        )
        self.assert_compile(
            parent.join(child),
            "%(test_schema)s.ptable JOIN "
            "%(test_schema)s.ctable "
            "ON %(test_schema)s.ptable.id = "
            "%(test_schema)s.ctable.parent_id"
            % {"test_schema": testing.config.test_schema},
        )


class ConstraintTest(fixtures.TablesTest):

    __only_on__ = "oracle"
    __backend__ = True
    run_deletes = None

    @classmethod
    def define_tables(cls, metadata):
        Table("foo", metadata, Column("id", Integer, primary_key=True))

    def test_oracle_has_no_on_update_cascade(self, connection):
        bar = Table(
            "bar",
            self.tables_test_metadata,
            Column("id", Integer, primary_key=True),
            Column(
                "foo_id", Integer, ForeignKey("foo.id", onupdate="CASCADE")
            ),
        )
        assert_warns(exc.SAWarning, bar.create, connection)

        bat = Table(
            "bat",
            self.tables_test_metadata,
            Column("id", Integer, primary_key=True),
            Column("foo_id", Integer),
            ForeignKeyConstraint(["foo_id"], ["foo.id"], onupdate="CASCADE"),
        )
        assert_warns(exc.SAWarning, bat.create, connection)

    def test_reflect_check_include_all(self, connection):
        insp = inspect(connection)
        eq_(insp.get_check_constraints("foo"), [])
        eq_(
            [
                rec["sqltext"]
                for rec in insp.get_check_constraints("foo", include_all=True)
            ],
            ['"ID" IS NOT NULL'],
        )


class SystemTableTablenamesTest(fixtures.TestBase):
    __only_on__ = "oracle"
    __backend__ = True

    def setup_test(self):

        with testing.db.begin() as conn:
            conn.exec_driver_sql("create table my_table (id integer)")
            conn.exec_driver_sql(
                "create global temporary table my_temp_table (id integer)",
            )
            conn.exec_driver_sql(
                "create table foo_table (id integer) tablespace SYSTEM"
            )

    def teardown_test(self):
        with testing.db.begin() as conn:
            conn.exec_driver_sql("drop table my_temp_table")
            conn.exec_driver_sql("drop table my_table")
            conn.exec_driver_sql("drop table foo_table")

    def test_table_names_no_system(self):
        insp = inspect(testing.db)
        eq_(insp.get_table_names(), ["my_table"])

    def test_temp_table_names_no_system(self):
        insp = inspect(testing.db)
        eq_(insp.get_temp_table_names(), ["my_temp_table"])

    def test_table_names_w_system(self):
        engine = testing_engine(options={"exclude_tablespaces": ["FOO"]})
        insp = inspect(engine)
        eq_(
            set(insp.get_table_names()).intersection(
                ["my_table", "foo_table"]
            ),
            set(["my_table", "foo_table"]),
        )

    def test_reflect_system_table(self):
        meta = MetaData()
        t = Table("foo_table", meta, autoload_with=testing.db)
        assert t.columns.keys() == ["id"]

        t = Table("my_temp_table", meta, autoload_with=testing.db)
        assert t.columns.keys() == ["id"]


class DontReflectIOTTest(fixtures.TestBase):
    """test that index overflow tables aren't included in
    table_names."""

    __only_on__ = "oracle"
    __backend__ = True

    def setup_test(self):
        with testing.db.begin() as conn:
            conn.exec_driver_sql(
                """
            CREATE TABLE admin_docindex(
                    token char(20),
                    doc_id NUMBER,
                    token_frequency NUMBER,
                    token_offsets VARCHAR2(2000),
                    CONSTRAINT pk_admin_docindex PRIMARY KEY (token, doc_id))
                ORGANIZATION INDEX
                TABLESPACE users
                PCTTHRESHOLD 20
                OVERFLOW TABLESPACE users
            """,
            )

    def teardown_test(self):
        with testing.db.begin() as conn:
            conn.exec_driver_sql("drop table admin_docindex")

    def test_reflect_all(self, connection):
        m = MetaData()
        m.reflect(connection)
        eq_(set(t.name for t in m.tables.values()), set(["admin_docindex"]))


def all_tables_compression_missing():
    with testing.db.connect() as conn:
        if (
            "Enterprise Edition"
            not in conn.exec_driver_sql("select * from v$version").scalar()
            # this works in Oracle Database 18c Express Edition Release
        ) and testing.db.dialect.server_version_info < (18,):
            return True
        return False


def all_tables_compress_for_missing():
    with testing.db.connect() as conn:
        if (
            "Enterprise Edition"
            not in conn.exec_driver_sql("select * from v$version").scalar()
        ):
            return True
        return False


class TableReflectionTest(fixtures.TestBase):
    __only_on__ = "oracle"
    __backend__ = True

    @testing.fails_if(all_tables_compression_missing)
    def test_reflect_basic_compression(self, metadata, connection):

        tbl = Table(
            "test_compress",
            metadata,
            Column("data", Integer, primary_key=True),
            oracle_compress=True,
        )
        metadata.create_all(connection)

        m2 = MetaData()

        tbl = Table("test_compress", m2, autoload_with=connection)
        # Don't hardcode the exact value, but it must be non-empty
        assert tbl.dialect_options["oracle"]["compress"]

    @testing.fails_if(all_tables_compress_for_missing)
    def test_reflect_oltp_compression(self, metadata, connection):
        tbl = Table(
            "test_compress",
            metadata,
            Column("data", Integer, primary_key=True),
            oracle_compress="OLTP",
        )
        metadata.create_all(connection)

        m2 = MetaData()

        tbl = Table("test_compress", m2, autoload_with=connection)
        assert tbl.dialect_options["oracle"]["compress"] == "OLTP"

    def test_reflect_hidden_column(self):
        with testing.db.begin() as conn:
            conn.exec_driver_sql(
                "CREATE TABLE my_table(id integer, hide integer INVISIBLE)"
            )

            try:
                insp = inspect(conn)
                cols = insp.get_columns("my_table")
                assert len(cols) == 1
                assert cols[0]["name"] == "id"
            finally:
                conn.exec_driver_sql("DROP TABLE my_table")


class ViewReflectionTest(fixtures.TestBase):
    __only_on__ = "oracle"
    __backend__ = True

    @classmethod
    def setup_test_class(cls):
        sql = """
    CREATE TABLE tbl (
        id INTEGER PRIMARY KEY,
        data INTEGER
    );

    CREATE VIEW tbl_plain_v AS
        SELECT id, data FROM tbl WHERE id > 100;

    -- comments on plain views are created with "comment on table"
    -- because why not..
    COMMENT ON TABLE tbl_plain_v IS 'view comment';

    CREATE MATERIALIZED VIEW tbl_v AS
        SELECT id, data FROM tbl WHERE id > 42;

    COMMENT ON MATERIALIZED VIEW tbl_v IS 'my mat view comment';

    CREATE MATERIALIZED VIEW tbl_v2 AS
        SELECT id, data FROM tbl WHERE id < 42;

    COMMENT ON MATERIALIZED VIEW tbl_v2 IS 'my other mat view comment';

    CREATE SYNONYM view_syn FOR tbl_plain_v;
    CREATE SYNONYM %(test_schema)s.ts_v_s FOR tbl_plain_v;

    CREATE VIEW %(test_schema)s.schema_view AS
        SELECT 1 AS value FROM dual;

    COMMENT ON TABLE %(test_schema)s.schema_view IS 'schema view comment';
    CREATE SYNONYM syn_schema_view FOR %(test_schema)s.schema_view;
    """
        if testing.requires.oracle_test_dblink.enabled:
            cls.dblink = config.file_config.get(
                "sqla_testing", "oracle_db_link"
            )
            sql += """
    CREATE SYNONYM syn_link FOR tbl_plain_v@%(link)s;
    """ % {
                "link": cls.dblink
            }
        with testing.db.begin() as conn:
            for stmt in (
                sql % {"test_schema": testing.config.test_schema}
            ).split(";"):
                if stmt.strip():
                    conn.exec_driver_sql(stmt)

    @classmethod
    def teardown_test_class(cls):
        sql = """
    DROP MATERIALIZED VIEW tbl_v;
    DROP MATERIALIZED VIEW tbl_v2;
    DROP VIEW tbl_plain_v;
    DROP TABLE tbl;
    DROP VIEW %(test_schema)s.schema_view;
    DROP SYNONYM view_syn;
    DROP SYNONYM %(test_schema)s.ts_v_s;
    DROP SYNONYM syn_schema_view;
    """
        if testing.requires.oracle_test_dblink.enabled:
            sql += """
    DROP SYNONYM syn_link;
    """
        with testing.db.begin() as conn:
            for stmt in (
                sql % {"test_schema": testing.config.test_schema}
            ).split(";"):
                if stmt.strip():
                    conn.exec_driver_sql(stmt)

    def test_get_names(self, connection):
        insp = inspect(connection)
        eq_(insp.get_table_names(), ["tbl"])
        eq_(insp.get_view_names(), ["tbl_plain_v"])
        eq_(insp.get_materialized_view_names(), ["tbl_v", "tbl_v2"])
        eq_(
            insp.get_view_names(schema=testing.config.test_schema),
            ["schema_view"],
        )

    def test_get_table_comment_on_view(self, connection):
        insp = inspect(connection)
        eq_(insp.get_table_comment("tbl_v"), {"text": "my mat view comment"})
        eq_(insp.get_table_comment("tbl_plain_v"), {"text": "view comment"})

    def test_get_multi_view_comment(self, connection):
        insp = inspect(connection)
        plain = {(None, "tbl_plain_v"): {"text": "view comment"}}
        mat = {
            (None, "tbl_v"): {"text": "my mat view comment"},
            (None, "tbl_v2"): {"text": "my other mat view comment"},
        }
        eq_(insp.get_multi_table_comment(kind=ObjectKind.VIEW), plain)
        eq_(
            insp.get_multi_table_comment(kind=ObjectKind.MATERIALIZED_VIEW),
            mat,
        )
        eq_(
            insp.get_multi_table_comment(kind=ObjectKind.ANY_VIEW),
            {**plain, **mat},
        )
        ts = testing.config.test_schema
        eq_(
            insp.get_multi_table_comment(kind=ObjectKind.ANY_VIEW, schema=ts),
            {(ts, "schema_view"): {"text": "schema view comment"}},
        )
        eq_(insp.get_multi_table_comment(), {(None, "tbl"): {"text": None}})

    def test_get_table_comment_synonym(self, connection):
        insp = inspect(connection)
        eq_(
            insp.get_table_comment("view_syn", oracle_resolve_synonyms=True),
            {"text": "view comment"},
        )
        eq_(
            insp.get_table_comment(
                "syn_schema_view", oracle_resolve_synonyms=True
            ),
            {"text": "schema view comment"},
        )
        eq_(
            insp.get_table_comment(
                "ts_v_s",
                oracle_resolve_synonyms=True,
                schema=testing.config.test_schema,
            ),
            {"text": "view comment"},
        )

    def test_get_multi_view_comment_synonym(self, connection):
        insp = inspect(connection)
        exp = {
            (None, "view_syn"): {"text": "view comment"},
            (None, "syn_schema_view"): {"text": "schema view comment"},
        }
        if testing.requires.oracle_test_dblink.enabled:
            exp[(None, "syn_link")] = {"text": "view comment"}
        eq_(
            insp.get_multi_table_comment(
                oracle_resolve_synonyms=True, kind=ObjectKind.ANY_VIEW
            ),
            exp,
        )
        ts = testing.config.test_schema
        eq_(
            insp.get_multi_table_comment(
                oracle_resolve_synonyms=True,
                schema=ts,
                kind=ObjectKind.ANY_VIEW,
            ),
            {(ts, "ts_v_s"): {"text": "view comment"}},
        )

    def test_get_view_definition(self, connection):
        insp = inspect(connection)
        eq_(
            insp.get_view_definition("tbl_plain_v"),
            "SELECT id, data FROM tbl WHERE id > 100",
        )
        eq_(
            insp.get_view_definition("tbl_v"),
            "SELECT id, data FROM tbl WHERE id > 42",
        )
        with expect_raises(exc.NoSuchTableError):
            eq_(insp.get_view_definition("view_syn"), None)
        eq_(
            insp.get_view_definition("view_syn", oracle_resolve_synonyms=True),
            "SELECT id, data FROM tbl WHERE id > 100",
        )
        eq_(
            insp.get_view_definition(
                "syn_schema_view", oracle_resolve_synonyms=True
            ),
            "SELECT 1 AS value FROM dual",
        )
        eq_(
            insp.get_view_definition(
                "ts_v_s",
                oracle_resolve_synonyms=True,
                schema=testing.config.test_schema,
            ),
            "SELECT id, data FROM tbl WHERE id > 100",
        )

    @testing.requires.oracle_test_dblink
    def test_get_view_definition_dblink(self, connection):
        insp = inspect(connection)
        eq_(
            insp.get_view_definition("syn_link", oracle_resolve_synonyms=True),
            "SELECT id, data FROM tbl WHERE id > 100",
        )
        eq_(
            insp.get_view_definition("tbl_plain_v", dblink=self.dblink),
            "SELECT id, data FROM tbl WHERE id > 100",
        )
        eq_(
            insp.get_view_definition("tbl_v", dblink=self.dblink),
            "SELECT id, data FROM tbl WHERE id > 42",
        )


class RoundTripIndexTest(fixtures.TestBase):
    __only_on__ = "oracle"
    __backend__ = True

    def test_no_pk(self, metadata, connection):
        Table(
            "sometable",
            metadata,
            Column("id_a", Unicode(255)),
            Column("id_b", Unicode(255)),
            Index("pk_idx_1", "id_a", "id_b", unique=True),
            Index("pk_idx_2", "id_b", "id_a", unique=True),
        )
        metadata.create_all(connection)

        insp = inspect(connection)
        eq_(
            insp.get_indexes("sometable"),
            [
                {
                    "name": "pk_idx_1",
                    "column_names": ["id_a", "id_b"],
                    "dialect_options": {},
                    "unique": True,
                },
                {
                    "name": "pk_idx_2",
                    "column_names": ["id_b", "id_a"],
                    "dialect_options": {},
                    "unique": True,
                },
            ],
        )

    @testing.combinations((True,), (False,), argnames="explicit_pk")
    def test_include_indexes_resembling_pk(
        self, metadata, connection, explicit_pk
    ):

        t = Table(
            "sometable",
            metadata,
            Column("id_a", Unicode(255), primary_key=True),
            Column("id_b", Unicode(255), primary_key=True),
            Column("group", Unicode(255), primary_key=True),
            Column("col", Unicode(255)),
            # Oracle won't let you do this unless the indexes have
            # the columns in different order
            Index("pk_idx_1", "id_b", "id_a", "group", unique=True),
            Index("pk_idx_2", "id_b", "group", "id_a", unique=True),
        )
        if explicit_pk:
            t.append_constraint(
                PrimaryKeyConstraint(
                    "id_a", "id_b", "group", name="some_primary_key"
                )
            )
        metadata.create_all(connection)

        insp = inspect(connection)
        eq_(
            insp.get_indexes("sometable"),
            [
                {
                    "name": "pk_idx_1",
                    "column_names": ["id_b", "id_a", "group"],
                    "dialect_options": {},
                    "unique": True,
                },
                {
                    "name": "pk_idx_2",
                    "column_names": ["id_b", "group", "id_a"],
                    "dialect_options": {},
                    "unique": True,
                },
            ],
        )

    def test_reflect_fn_index(self, metadata, connection):
        """test reflection of a functional index.

        it appears this emitted a warning at some point but does not right now.
        the returned data is not exactly correct, but this is what it's
        likely been doing for many years.

        """

        s_table = Table(
            "sometable",
            metadata,
            Column("group", Unicode(255), primary_key=True),
            Column("col", Unicode(255)),
        )

        Index("data_idx", func.upper(s_table.c.col))

        metadata.create_all(connection)

        eq_(
            inspect(connection).get_indexes("sometable"),
            [
                {
                    "column_names": [],
                    "dialect_options": {},
                    "name": "data_idx",
                    "unique": False,
                }
            ],
        )

    def test_basic(self, metadata, connection):

        s_table = Table(
            "sometable",
            metadata,
            Column("id_a", Unicode(255), primary_key=True),
            Column("id_b", Unicode(255), primary_key=True, unique=True),
            Column("group", Unicode(255), primary_key=True),
            Column("col", Unicode(255)),
            UniqueConstraint("col", "group"),
        )

        # "group" is a keyword, so lower case
        normalind = Index("tableind", s_table.c.id_b, s_table.c.group)
        Index(
            "compress1", s_table.c.id_a, s_table.c.id_b, oracle_compress=True
        )
        Index(
            "compress2",
            s_table.c.id_a,
            s_table.c.id_b,
            s_table.c.col,
            oracle_compress=1,
        )

        metadata.create_all(connection)

        mirror = MetaData()
        mirror.reflect(connection)

        metadata.drop_all(connection)
        mirror.create_all(connection)

        inspect = MetaData()
        inspect.reflect(connection)

        def obj_definition(obj):
            return (
                obj.__class__,
                tuple([c.name for c in obj.columns]),
                getattr(obj, "unique", None),
            )

        # find what the primary k constraint name should be
        primaryconsname = connection.scalar(
            text(
                """SELECT constraint_name
               FROM all_constraints
               WHERE table_name = :table_name
               AND owner = :owner
               AND constraint_type = 'P' """
            ),
            dict(
                table_name=s_table.name.upper(),
                owner=testing.db.dialect.default_schema_name.upper(),
            ),
        )

        reflectedtable = inspect.tables[s_table.name]

        # make a dictionary of the reflected objects:

        reflected = dict(
            [
                (obj_definition(i), i)
                for i in reflectedtable.indexes | reflectedtable.constraints
            ]
        )

        # assert we got primary key constraint and its name, Error
        # if not in dict

        assert (
            reflected[
                (PrimaryKeyConstraint, ("id_a", "id_b", "group"), None)
            ].name.upper()
            == primaryconsname.upper()
        )

        # Error if not in dict

        eq_(reflected[(Index, ("id_b", "group"), False)].name, normalind.name)
        assert (Index, ("id_b",), True) in reflected
        assert (Index, ("col", "group"), True) in reflected

        idx = reflected[(Index, ("id_a", "id_b"), False)]
        assert idx.dialect_options["oracle"]["compress"] == 2

        idx = reflected[(Index, ("id_a", "id_b", "col"), False)]
        assert idx.dialect_options["oracle"]["compress"] == 1

        eq_(len(reflectedtable.constraints), 1)
        eq_(len(reflectedtable.indexes), 5)


class DBLinkReflectionTest(fixtures.TestBase):
    __requires__ = ("oracle_test_dblink",)
    __only_on__ = "oracle"
    __backend__ = True

    @classmethod
    def setup_test_class(cls):
        cls.dblink = config.file_config.get("sqla_testing", "oracle_db_link")

        # note that the synonym here is still not totally functional
        # when accessing via a different username as we do with the
        # multiprocess test suite, so testing here is minimal
        with testing.db.begin() as conn:
            conn.exec_driver_sql(
                "create table test_table "
                "(id integer primary key, data varchar2(50))"
            )
            conn.exec_driver_sql(
                "create synonym test_table_syn "
                "for test_table@%s" % cls.dblink
            )

    @classmethod
    def teardown_test_class(cls):
        with testing.db.begin() as conn:
            conn.exec_driver_sql("drop synonym test_table_syn")
            conn.exec_driver_sql("drop table test_table")

    def test_reflection(self):
        """test the resolution of the synonym/dblink."""
        m = MetaData()

        t = Table(
            "test_table_syn",
            m,
            autoload_with=testing.db,
            oracle_resolve_synonyms=True,
        )
        eq_(list(t.c.keys()), ["id", "data"])
        eq_(list(t.primary_key), [t.c.id])


class TypeReflectionTest(fixtures.TestBase):
    __only_on__ = "oracle"
    __backend__ = True

    def _run_test(self, metadata, connection, specs, attributes):
        columns = [Column("c%i" % (i + 1), t[0]) for i, t in enumerate(specs)]
        m = metadata
        Table("oracle_types", m, *columns)
        m.create_all(connection)
        m2 = MetaData()
        table = Table("oracle_types", m2, autoload_with=connection)
        for i, (reflected_col, spec) in enumerate(zip(table.c, specs)):
            expected_spec = spec[1]
            reflected_type = reflected_col.type
            is_(type(reflected_type), type(expected_spec), spec[0])
            for attr in attributes:
                r_attr = getattr(reflected_type, attr)
                e_attr = getattr(expected_spec, attr)
                col = f"c{i+1}"
                eq_(
                    r_attr,
                    e_attr,
                    f"Column {col}: Attribute {attr} value of {r_attr} "
                    f"does not match {e_attr} for type {spec[0]}",
                )
                eq_(
                    type(r_attr),
                    type(e_attr),
                    f"Column {col}: Attribute {attr} type do not match "
                    f"{type(r_attr)} != {type(e_attr)} for db type {spec[0]}",
                )

    def test_integer_types(self, metadata, connection):
        specs = [(Integer, INTEGER()), (Numeric, INTEGER())]
        self._run_test(metadata, connection, specs, [])

    def test_number_types(
        self,
        metadata,
        connection,
    ):
        specs = [(Numeric(5, 2), NUMBER(5, 2)), (NUMBER, NUMBER())]
        self._run_test(metadata, connection, specs, ["precision", "scale"])

    def test_float_types(
        self,
        metadata,
        connection,
    ):
        specs = [
            (DOUBLE_PRECISION(), DOUBLE_PRECISION()),
            (Double(), DOUBLE_PRECISION()),
            (REAL(), REAL()),
            (BINARY_DOUBLE(), BINARY_DOUBLE()),
            (BINARY_FLOAT(), BINARY_FLOAT()),
            (oracle.FLOAT(5), oracle.FLOAT(5)),
            (
                Float(5).with_variant(
                    oracle.FLOAT(binary_precision=16), "oracle"
                ),
                oracle.FLOAT(16),
            ),  # using conversion
            (FLOAT(), DOUBLE_PRECISION()),
            # from https://docs.oracle.com/cd/B14117_01/server.101/b10758/sqlqr06.htm  # noqa: E501
            # DOUBLE PRECISION == precision 126
            # REAL == precision 63
            (oracle.FLOAT(126), DOUBLE_PRECISION()),
            (oracle.FLOAT(63), REAL()),
        ]
        self._run_test(metadata, connection, specs, ["precision"])

    def test_string_types(
        self,
        metadata,
        connection,
    ):
        specs = [
            (String(125), VARCHAR(125)),
            (String(42).with_variant(VARCHAR2(42), "oracle"), VARCHAR(42)),
            (Unicode(125), VARCHAR(125)),
            (Unicode(42).with_variant(NVARCHAR2(42), "oracle"), NVARCHAR(42)),
            (CHAR(125), CHAR(125)),
            (NCHAR(42), NCHAR(42)),
        ]
        self._run_test(metadata, connection, specs, ["length"])


class IdentityReflectionTest(fixtures.TablesTest):
    __only_on__ = "oracle"
    __backend__ = True
    __requires__ = ("identity_columns",)

    @classmethod
    def define_tables(cls, metadata):
        Table("t1", metadata, Column("id1", Integer, Identity(on_null=True)))
        Table("t2", metadata, Column("id2", Integer, Identity(order=True)))

    def test_reflect_identity(self):
        insp = inspect(testing.db)
        common = {
            "always": False,
            "start": 1,
            "increment": 1,
            "on_null": False,
            "maxvalue": 10**28 - 1,
            "minvalue": 1,
            "cycle": False,
            "cache": 20,
            "order": False,
        }
        for col in insp.get_columns("t1") + insp.get_columns("t2"):
            if col["name"] == "id1":
                is_true("identity" in col)
                exp = common.copy()
                exp["on_null"] = True
                eq_(col["identity"], exp)
            if col["name"] == "id2":
                is_true("identity" in col)
                exp = common.copy()
                exp["order"] = True
                eq_(col["identity"], exp)


class AdditionalReflectionTests(fixtures.TestBase):
    __only_on__ = "oracle"
    __backend__ = True

    @classmethod
    def setup_test_class(cls):
        # currently assuming full DBA privs for the user.
        # don't really know how else to go here unless
        # we connect as the other user.

        sql = """
CREATE TABLE %(schema)sparent(
    id INTEGER,
    data VARCHAR2(50),
    CONSTRAINT parent_pk_%(schema_id)s PRIMARY KEY (id)
);
CREATE TABLE %(schema)smy_table(
    id INTEGER,
    name VARCHAR2(125),
    related INTEGER,
    data%(schema_id)s NUMBER NOT NULL,
    CONSTRAINT my_table_pk_%(schema_id)s PRIMARY KEY (id),
    CONSTRAINT my_table_fk_%(schema_id)s FOREIGN KEY(related)
    REFERENCES %(schema)sparent(id),
    CONSTRAINT my_table_check_%(schema_id)s CHECK (data%(schema_id)s > 42),
    CONSTRAINT data_unique%(schema_id)s UNIQUE (data%(schema_id)s)
);
CREATE INDEX my_table_index_%(schema_id)s on %(schema)smy_table (id, name);
COMMENT ON TABLE %(schema)smy_table IS 'my table comment %(schema_id)s';
COMMENT ON COLUMN %(schema)smy_table.name IS
'my table.name comment %(schema_id)s';
"""

        with testing.db.begin() as conn:
            for schema in ("", testing.config.test_schema):
                dd = {
                    "schema": f"{schema}." if schema else "",
                    "schema_id": "sch" if schema else "",
                }
                for stmt in (sql % dd).split(";"):
                    if stmt.strip():
                        conn.exec_driver_sql(stmt)

    @classmethod
    def teardown_test_class(cls):
        sql = """
drop table %(schema)smy_table;
drop table %(schema)sparent;
"""
        with testing.db.begin() as conn:
            for schema in ("", testing.config.test_schema):
                dd = {"schema": f"{schema}." if schema else ""}
                for stmt in (sql % dd).split(";"):
                    if stmt.strip():
                        try:
                            conn.exec_driver_sql(stmt)
                        except:
                            pass

    def setup_test(self):
        self.dblink = config.file_config.get("sqla_testing", "oracle_db_link")
        self.dblink2 = config.file_config.get(
            "sqla_testing", "oracle_db_link2"
        )
        self.columns = {}
        self.indexes = {}
        self.primary_keys = {}
        self.comments = {}
        self.uniques = {}
        self.checks = {}
        self.foreign_keys = {}
        self.options = {}
        self.allDicts = [
            self.columns,
            self.indexes,
            self.primary_keys,
            self.comments,
            self.uniques,
            self.checks,
            self.foreign_keys,
            self.options,
        ]
        for schema in (None, testing.config.test_schema):
            suffix = "sch" if schema else ""

            self.columns[schema] = {
                (schema, "my_table"): [
                    {
                        "name": "id",
                        "nullable": False,
                        "type": eq_compile_type("INTEGER"),
                        "default": None,
                        "comment": None,
                    },
                    {
                        "name": "name",
                        "nullable": True,
                        "type": eq_compile_type("VARCHAR(125)"),
                        "default": None,
                        "comment": f"my table.name comment {suffix}",
                    },
                    {
                        "name": "related",
                        "nullable": True,
                        "type": eq_compile_type("INTEGER"),
                        "default": None,
                        "comment": None,
                    },
                    {
                        "name": f"data{suffix}",
                        "nullable": False,
                        "type": eq_compile_type("NUMBER"),
                        "default": None,
                        "comment": None,
                    },
                ],
                (schema, "parent"): [
                    {
                        "name": "id",
                        "nullable": False,
                        "type": eq_compile_type("INTEGER"),
                        "default": None,
                        "comment": None,
                    },
                    {
                        "name": "data",
                        "nullable": True,
                        "type": eq_compile_type("VARCHAR(50)"),
                        "default": None,
                        "comment": None,
                    },
                ],
            }
            self.indexes[schema] = {
                (schema, "my_table"): [
                    {
                        "name": f"data_unique{suffix}",
                        "column_names": [f"data{suffix}"],
                        "dialect_options": {},
                        "unique": True,
                    },
                    {
                        "name": f"my_table_index_{suffix}",
                        "column_names": ["id", "name"],
                        "dialect_options": {},
                        "unique": False,
                    },
                ],
                (schema, "parent"): [],
            }
            self.primary_keys[schema] = {
                (schema, "my_table"): {
                    "name": f"my_table_pk_{suffix}",
                    "constrained_columns": ["id"],
                },
                (schema, "parent"): {
                    "name": f"parent_pk_{suffix}",
                    "constrained_columns": ["id"],
                },
            }
            self.comments[schema] = {
                (schema, "my_table"): {"text": f"my table comment {suffix}"},
                (schema, "parent"): {"text": None},
            }
            self.foreign_keys[schema] = {
                (schema, "my_table"): [
                    {
                        "name": f"my_table_fk_{suffix}",
                        "constrained_columns": ["related"],
                        "referred_schema": schema,
                        "referred_table": "parent",
                        "referred_columns": ["id"],
                        "options": {},
                    }
                ],
                (schema, "parent"): [],
            }
            self.checks[schema] = {
                (schema, "my_table"): [
                    {
                        "name": f"my_table_check_{suffix}",
                        "sqltext": f"data{suffix} > 42",
                    }
                ],
                (schema, "parent"): [],
            }
            self.uniques[schema] = {
                (schema, "my_table"): [
                    {
                        "name": f"data_unique{suffix}",
                        "column_names": [f"data{suffix}"],
                        "duplicates_index": f"data_unique{suffix}",
                    }
                ],
                (schema, "parent"): [],
            }
            self.options[schema] = {
                (schema, "my_table"): {},
                (schema, "parent"): {},
            }

    def test_tables(self, connection):
        insp = inspect(connection)

        eq_(sorted(insp.get_table_names()), ["my_table", "parent"])

    def _check_reflection(self, conn, schema, res_schema=False, **kw):
        if res_schema is False:
            res_schema = schema
        insp = inspect(conn)
        eq_(
            insp.get_multi_columns(schema=schema, **kw),
            self.columns[res_schema],
        )
        eq_(
            insp.get_multi_indexes(schema=schema, **kw),
            self.indexes[res_schema],
        )
        eq_(
            insp.get_multi_pk_constraint(schema=schema, **kw),
            self.primary_keys[res_schema],
        )
        eq_(
            insp.get_multi_table_comment(schema=schema, **kw),
            self.comments[res_schema],
        )
        eq_(
            insp.get_multi_foreign_keys(schema=schema, **kw),
            self.foreign_keys[res_schema],
        )
        eq_(
            insp.get_multi_check_constraints(schema=schema, **kw),
            self.checks[res_schema],
        )
        eq_(
            insp.get_multi_unique_constraints(schema=schema, **kw),
            self.uniques[res_schema],
        )
        eq_(
            insp.get_multi_table_options(schema=schema, **kw),
            self.options[res_schema],
        )

    @testing.combinations(True, False, argnames="schema")
    def test_schema_translate_map(self, connection, schema):
        schema = testing.config.test_schema if schema else None
        c = connection.execution_options(
            schema_translate_map={
                None: "foo",
                testing.config.test_schema: "bar",
            }
        )
        self._check_reflection(c, schema)

    @testing.requires.oracle_test_dblink
    def test_db_link(self, connection):
        self._check_reflection(connection, schema=None, dblink=self.dblink)
        self._check_reflection(
            connection,
            schema=testing.config.test_schema,
            dblink=self.dblink,
        )

    def test_no_synonyms(self, connection):
        # oracle_resolve_synonyms is ignored if there are no matching synonym
        self._check_reflection(
            connection, schema=None, oracle_resolve_synonyms=True
        )
        connection.exec_driver_sql("CREATE SYNONYM tmp FOR parent")
        for dict_ in self.allDicts:
            dict_["tmp"] = {(None, "parent"): dict_[None][(None, "parent")]}
        try:
            self._check_reflection(
                connection,
                schema=None,
                res_schema="tmp",
                oracle_resolve_synonyms=True,
                filter_names=["parent"],
            )
        finally:
            connection.exec_driver_sql("DROP SYNONYM tmp")

    @testing.requires.oracle_test_dblink
    @testing.requires.oracle_test_dblink2
    def test_multi_dblink_synonyms(self, connection):
        # oracle_resolve_synonyms handles multiple dblink at once
        connection.exec_driver_sql(
            f"CREATE SYNONYM s1 FOR my_table@{self.dblink}"
        )
        connection.exec_driver_sql(
            f"CREATE SYNONYM s2 FOR {testing.config.test_schema}."
            f"my_table@{self.dblink2}"
        )
        connection.exec_driver_sql("CREATE SYNONYM s3 FOR parent")
        for dict_ in self.allDicts:
            dict_["tmp"] = {
                (None, "s1"): dict_[None][(None, "my_table")],
                (None, "s2"): dict_[testing.config.test_schema][
                    (testing.config.test_schema, "my_table")
                ],
                (None, "s3"): dict_[None][(None, "parent")],
            }
        fk = self.foreign_keys["tmp"][(None, "s1")][0]
        fk["referred_table"] = "s3"
        try:
            self._check_reflection(
                connection,
                schema=None,
                res_schema="tmp",
                oracle_resolve_synonyms=True,
            )
        finally:
            connection.exec_driver_sql("DROP SYNONYM s1")
            connection.exec_driver_sql("DROP SYNONYM s2")
            connection.exec_driver_sql("DROP SYNONYM s3")
