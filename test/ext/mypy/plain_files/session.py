from __future__ import annotations

from typing import List

from sqlalchemy import create_engine
from sqlalchemy import ForeignKey
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.orm import relationship
from sqlalchemy.orm import Session


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    addresses: Mapped[List[Address]] = relationship(back_populates="user")


class Address(Base):
    __tablename__ = "address"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id = mapped_column(ForeignKey("user.id"))
    email: Mapped[str]

    user: Mapped[User] = relationship(back_populates="addresses")


e = create_engine("sqlite://")
Base.metadata.create_all(e)

with Session(e) as sess:
    u1 = User(name="u1")
    sess.add(u1)
    sess.add_all([Address(user=u1, email="e1"), Address(user=u1, email="e2")])
    sess.commit()

    q = sess.query(User).filter_by(id=7)

    # EXPECTED_TYPE: Query[User]
    reveal_type(q)

    rows1 = q.all()

    # EXPECTED_RE_TYPE: builtins.[Ll]ist\[.*User\*?\]
    reveal_type(rows1)

    q2 = sess.query(User.id).filter_by(id=7)
    rows2 = q2.all()

    # EXPECTED_TYPE: List[Row[Tuple[int]]]
    reveal_type(rows2)

    # test #8280

    sess.query(User).update(
        {"name": User.name + " some name"}, synchronize_session="fetch"
    )
    sess.query(User).update(
        {"name": User.name + " some name"}, synchronize_session=False
    )
    sess.query(User).update(
        {"name": User.name + " some name"}, synchronize_session="evaluate"
    )

    sess.query(User).update(
        {"name": User.name + " some name"},
        # EXPECTED_MYPY: Argument "synchronize_session" to "update" of "Query" has incompatible type  # noqa: E501
        synchronize_session="invalid",
    )
    sess.query(User).update({"name": User.name + " some name"})

# more result tests in typed_results.py
