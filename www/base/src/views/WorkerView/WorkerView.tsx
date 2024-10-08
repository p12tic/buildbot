/*
  This file is part of Buildbot.  Buildbot is free software: you can
  redistribute it and/or modify it under the terms of the GNU General Public
  License as published by the Free Software Foundation, version 2.

  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
  FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
  details.

  You should have received a copy of the GNU General Public License along with
  this program; if not, write to the Free Software Foundation, Inc., 51
  Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

  Copyright Buildbot Team Members
*/

import {useState} from "react";
import {observer} from "mobx-react";
import {
  Build,
  Builder,
  Master,
  Worker,
  useDataAccessor,
  useDataApiQuery,
  useDataApiDynamicQuery
} from "buildbot-data-js";
import {useParams} from "react-router-dom";
import {buildbotSetupPlugin} from "buildbot-plugin-support";
import {getBuildLinkDisplayProperties, TopbarAction, useLoadMoreItemsState, useTopbarActions} from "buildbot-ui";
import {WorkersTable} from "../../components/WorkersTable/WorkersTable";
import {BuildsTable} from "../../components/BuildsTable/BuildsTable";
import {WorkerActionsModal} from "../../components/WorkerActionsModal/WorkerActionsModal";

export const WorkerView = observer(() => {
  const workerid = Number.parseInt(useParams<"workerid">().workerid ?? "");
  const accessor = useDataAccessor([workerid]);

  const initialBuildsFetchLimit = 100;
  const [buildsFetchLimit, onLoadMoreBuilds] =
      useLoadMoreItemsState(initialBuildsFetchLimit, initialBuildsFetchLimit);

  const workersQuery = useDataApiQuery(() => Worker.getAll(accessor, {id: workerid.toString()}));
  const buildersQuery = useDataApiQuery(() => Builder.getAll(accessor));
  const mastersQuery = useDataApiQuery(() => Master.getAll(accessor));
  const buildsQuery = useDataApiDynamicQuery([buildsFetchLimit], () =>
    Build.getAll(accessor, {query: {
        property: ["owners", "workername", "branch", "revision", ...getBuildLinkDisplayProperties()],
        workerid__eq: workerid,
        limit: buildsFetchLimit,
        order: "-buildid",
      }
    }));

  const [workerForActions, setWorkerForActions] = useState<null|Worker>(null);

  const topBarActions: TopbarAction[] = [];
  if (workersQuery.isResolved() && workersQuery.array.length >= 1) {
    topBarActions.push(
      {
        caption: "Actions...",
        variant: "primary",
        action: () => {
          setWorkerForActions(workersQuery.array[0]);
        },
      });
  }
  useTopbarActions(topBarActions);

  return (
    <div className="container">
      <WorkersTable workers={workersQuery.array} buildersQuery={buildersQuery}
                    mastersQuery={mastersQuery}
                    buildsForWorker={null}
                    onWorkerIconClick={(worker) => setWorkerForActions(worker)}/>
      { workerForActions !== null
        ? <WorkerActionsModal worker={workerForActions}
                              onClose={() => setWorkerForActions(null)}/>
        : <></>
      }
      <BuildsTable builds={buildsQuery} builders={buildersQuery} fetchLimit={buildsFetchLimit}
                   onLoadMore={onLoadMoreBuilds}/>
    </div>
  );
});

buildbotSetupPlugin((reg) => {
  reg.registerRoute({
    route: "workers/:workerid",
    group: "workers",
    element: () => <WorkerView/>,
  });
});
