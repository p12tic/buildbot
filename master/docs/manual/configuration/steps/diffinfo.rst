.. bb:step:: DiffInfo

.. _Step-DiffInfo:

DiffInfo
++++++++

The `DiffInfo` step gathers information about differences between the current revision and the last common ancestor of this revision and another commit or branch.
This information is useful for various reporters to be able to identify new warnings that appear in newly modified code.
The diff information is stored as a custom json as transient build data via ``setBuildData`` function.

Currently only git repositories are supported.

The class inherits the arguments accepted by ``ShellMixin`` except ``command``.

Additionally, it accepts the following arguments:

``compareToRef``
    (Optional, string, defaults to ``master``)
    The commit or branch identifying the revision to get the last common ancestor to.
    In most cases, this will be the target branch of a pull or merge request.

``dataName``
    (Optional, string, defaults to ``diffinfo-master``)
    The name of the build data to save the diff json to.
