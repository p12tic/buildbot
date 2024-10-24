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

from typing import TYPE_CHECKING
from typing import Generator

from twisted.internet import defer

from buildbot.db import buildrequests
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.util import datetime2epoch

if TYPE_CHECKING:
    from buildbot.db.sourcestamps import SourceStampModel


class BuildRequest(Row):
    table = "buildrequests"

    foreignKeys = ('buildsetid',)

    id_column = 'id'
    required_columns = ('buildsetid',)

    def __init__(
        self,
        id=None,
        buildsetid=None,
        builderid=None,
        priority=0,
        complete=0,
        results=-1,
        submitted_at=12345678,
        complete_at=None,
        waited_for=0,
    ):
        super().__init__(
            id=id,
            buildsetid=buildsetid,
            builderid=builderid,
            priority=priority,
            complete=complete,
            results=results,
            submitted_at=submitted_at,
            complete_at=complete_at,
            waited_for=waited_for,
        )


class BuildRequestClaim(Row):
    table = "buildrequest_claims"

    foreignKeys = ('brid', 'masterid')

    required_columns = ('brid', 'masterid', 'claimed_at')

    def __init__(self, brid=None, masterid=None, claimed_at=None):
        super().__init__(brid=brid, masterid=masterid, claimed_at=claimed_at)


class FakeBuildRequestsComponent(FakeDBComponent):
    # for use in determining "my" requests
    MASTER_ID = 824

    def setUp(self):
        self.reqs = {}
        self.claims = {}

    def insert_test_data(self, rows):
        for row in rows:
            if isinstance(row, BuildRequest):
                self.reqs[row.id] = row

            if isinstance(row, BuildRequestClaim):
                self.claims[row.brid] = row

    # component methods
    @defer.inlineCallbacks
    def getBuildRequest(self, brid: int):
        row = self.reqs.get(brid)
        if not row:
            return None

        claim_row = self.claims.get(brid, None)
        if claim_row:
            row.claimed_at = claim_row.claimed_at
            row.claimed = True
            row.masterid = claim_row.masterid
            row.claimed_by_masterid = claim_row.masterid
        else:
            row.claimed_at = None
            row.masterid = None
        builder = yield self.db.builders.getBuilder(row.builderid)
        row.buildername = builder.name
        return self._modelFromRow(row)

    @defer.inlineCallbacks
    def getBuildRequests(
        self,
        builderid: int | None = None,
        complete: bool | None = None,
        claimed: bool | int | None = None,
        bsid: int | None = None,
        branch: str | None = None,
        repository: str | None = None,
        resultSpec: dict | None = None,
    ) -> Generator[defer.Deferred[str], None, list[buildrequests.BuildRequestModel]]:
        rv: list[buildrequests.BuildRequestModel] = []
        for br in self.reqs.values():
            if builderid and br.builderid != builderid:
                continue
            if complete is not None:
                if complete and not br.complete:
                    continue
                if not complete and br.complete:
                    continue
            claim_row = self.claims.get(br.id)
            if claim_row:
                br.claimed_at = claim_row.claimed_at
                br.claimed = True
                br.masterid = claim_row.masterid
                br.claimed_by_masterid = claim_row.masterid
            else:
                br.claimed_at = None
                br.masterid = None
            if claimed is not None:
                if isinstance(claimed, bool):
                    if claimed:
                        if not claim_row:
                            continue
                    else:
                        if br.complete or claim_row:
                            continue
                else:
                    if not claim_row or claim_row.masterid != claimed:
                        continue
            if bsid is not None:
                if br.buildsetid != bsid:
                    continue

            if branch or repository:
                buildset = yield self.db.buildsets.getBuildset(br.buildsetid)
                sourcestamps: list[SourceStampModel] = []
                assert buildset is not None
                for ssid in buildset.sourcestamps:
                    sourcestamps.append((yield self.db.sourcestamps.getSourceStamp(ssid)))

                if branch and not any(branch == s.branch for s in sourcestamps):
                    continue
                if repository and not any(repository == s.repository for s in sourcestamps):
                    continue
            builder = yield self.db.builders.getBuilder(br.builderid)
            assert builder is not None
            br.buildername = builder.name
            rv.append(self._modelFromRow(br))
        if resultSpec is not None:
            rv = self.applyResultSpec(rv, resultSpec)
        return rv

    def claimBuildRequests(self, brids, claimed_at=None):
        if claimed_at is not None:
            claimed_at = datetime2epoch(claimed_at)
        else:
            claimed_at = int(self.reactor.seconds())

        return self._claim_buildrequests_for_master(brids, claimed_at, self.MASTER_ID)

    def _claim_buildrequests_for_master(self, brids, claimed_at, masterid):
        for brid in brids:
            if brid not in self.reqs or brid in self.claims:
                raise buildrequests.AlreadyClaimedError

        for brid in brids:
            self.claims[brid] = BuildRequestClaim(
                brid=brid, masterid=masterid, claimed_at=claimed_at
            )
        return defer.succeed(None)

    def unclaimBuildRequests(self, brids):
        self._unclaim_buildrequests_for_master(brids, self.db.master.masterid)

    def _unclaim_buildrequests_for_master(self, brids, masterid):
        for brid in brids:
            if brid in self.claims and self.claims[brid].masterid == masterid:
                self.claims.pop(brid)

    def completeBuildRequests(self, brids, results, complete_at=None):
        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = int(self.reactor.seconds())

        for brid in brids:
            if brid not in self.reqs or self.reqs[brid].complete == 1:
                raise buildrequests.NotClaimedError

        for brid in brids:
            self.reqs[brid].complete = 1
            self.reqs[brid].results = results
            self.reqs[brid].complete_at = complete_at
        return defer.succeed(None)

    def _modelFromRow(self, row):
        return buildrequests.BuildRequestsConnectorComponent._modelFromRow(row)
