# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import annotations

from twisted.internet import defer

from buildbot.db.users import UserModel
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row


class User(Row):
    table = "users"

    id_column = 'uid'

    def __init__(self, uid=None, identifier='soap', bb_username=None, bb_password=None):
        super().__init__(
            uid=uid, identifier=identifier, bb_username=bb_username, bb_password=bb_password
        )


class UserInfo(Row):
    table = "users_info"

    foreignKeys = ('uid',)
    required_columns = ('uid',)

    def __init__(self, uid=None, attr_type='git', attr_data='Tyler Durden <tyler@mayhem.net>'):
        super().__init__(uid=uid, attr_type=attr_type, attr_data=attr_data)


class FakeUsersComponent(FakeDBComponent):
    def setUp(self):
        self.users = {}
        self.users_info = {}
        self.id_num = 0

    def insert_test_data(self, rows):
        for row in rows:
            if isinstance(row, User):
                self.users[row.uid] = {
                    "identifier": row.identifier,
                    "bb_username": row.bb_username,
                    "bb_password": row.bb_password,
                }

            if isinstance(row, UserInfo):
                assert row.uid in self.users
                if row.uid not in self.users_info:
                    self.users_info[row.uid] = [
                        {"attr_type": row.attr_type, "attr_data": row.attr_data}
                    ]
                else:
                    self.users_info[row.uid].append({
                        "attr_type": row.attr_type,
                        "attr_data": row.attr_data,
                    })

    def _model_from_uid(self, uid: int, fetch_attributes: bool = True) -> UserModel | None:
        model = None
        if uid in self.users:
            usdict = self.users[uid]
            model = UserModel(
                uid=uid,
                identifier=usdict['identifier'],
                bb_username=usdict.get('bb_username'),
                bb_password=usdict.get('bb_password'),
                attributes=None,
            )
            if fetch_attributes and uid in self.users_info:
                infos = self.users_info[uid]
                attributes = {}
                for attr in infos:
                    attributes[attr['attr_type']] = attr['attr_data']
                model.attributes = attributes

        return model

    def nextId(self):
        self.id_num += 1
        return self.id_num

    # component methods

    @defer.inlineCallbacks
    def findUserByAttr(self, identifier, attr_type, attr_data):
        for uid, attrs in self.users_info.items():
            for attr in attrs:
                if attr_type == attr['attr_type'] and attr_data == attr['attr_data']:
                    return defer.succeed(uid)

        uid = self.nextId()
        yield self.db.insert_test_data([User(uid=uid, identifier=identifier)])
        yield self.db.insert_test_data([
            UserInfo(uid=uid, attr_type=attr_type, attr_data=attr_data)
        ])
        return uid

    def getUser(self, uid) -> defer.Deferred[UserModel | None]:
        usdict = None
        if uid in self.users:
            usdict = self._model_from_uid(uid)
        return defer.succeed(usdict)

    def getUsers(self) -> defer.Deferred[list[UserModel]]:
        return defer.succeed([
            self._model_from_uid(uid, fetch_attributes=False)
            for uid in sorted(list(self.users.keys()))
        ])

    def getUserByUsername(self, username) -> defer.Deferred[UserModel | None]:
        usdict = None
        for uid, user in self.users.items():
            if user['bb_username'] == username:
                usdict = self._model_from_uid(uid)
        return defer.succeed(usdict)

    def updateUser(
        self,
        uid=None,
        identifier=None,
        bb_username=None,
        bb_password=None,
        attr_type=None,
        attr_data=None,
    ):
        assert uid is not None

        if identifier is not None:
            self.users[uid]['identifier'] = identifier

        if bb_username is not None:
            assert bb_password is not None
            try:
                user = self.users[uid]
                user['bb_username'] = bb_username
                user['bb_password'] = bb_password
            except KeyError:
                pass

        if attr_type is not None:
            assert attr_data is not None
            try:
                infos = self.users_info[uid]
                for attr in infos:
                    if attr_type == attr['attr_type']:
                        attr['attr_data'] = attr_data
                        break
                else:
                    infos.append({"attr_type": attr_type, "attr_data": attr_data})
            except KeyError:
                pass

        return defer.succeed(None)

    def removeUser(self, uid):
        if uid in self.users:
            self.users.pop(uid)
            self.users_info.pop(uid)
        return defer.succeed(None)

    def identifierToUid(self, identifier):
        for uid, user in self.users.items():
            if identifier == user['identifier']:
                return defer.succeed(uid)
        return defer.succeed(None)
