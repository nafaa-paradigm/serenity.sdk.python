import json

from datetime import datetime
from typing import List, Optional, TypeVar
from uuid import UUID

from serenity_sdk.api.core import SerenityApi
from serenity_sdk.client.raw import CallType, SerenityClient
from serenity_sdk.types.common import STD_DATE_FMT
from serenity_types.risk.scenarios import (ScenarioCloneRequest, ScenarioDefinition,
                                           ScenarioRequest, ScenarioResult, ScenarioRun)
from serenity_types.utils.common import Response


T = TypeVar('T')


class ScenariosApi(SerenityApi):
    """
    The scenarios API group covers stress testing facilities.
    """

    def __init__(self, client: SerenityClient):
        """
        :param client: the raw client to delegate to when making API calls
        """
        super().__init__(client, 'risk/scenarios')

    def clone_scenario(self, request: ScenarioCloneRequest) -> Response[ScenarioDefinition]:
        """
        Given the UUID for a custom or predefined scenario, makes a copy and creates a new custom scenario,
        allocating a UUID for it.

        :param request: details of the scenario to clone, including new cloned scenario name.
        :return: cloned definition, including newly-allocated UUID and with the ownerId updated to the user
                 who did the clone operation
        """
        request_json = json.loads(request.json(exclude_unset=True, by_alias=True))
        raw_json = self._call_api('/clone', params={}, body_json=request_json, call_type=CallType.POST)
        result = ScenarioDefinition.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    def create_custom_scenario(self, request: ScenarioDefinition) -> Response[ScenarioDefinition]:
        """
        Creates a new custom scenario and allocates a UUID for it.

        :param request: the initial definition to create, with no UUID or version number
        :return: updated definition with new version number, updated lastUpdated and lastUpdatedBy fields
        """
        request_json = json.loads(request.json(exclude_unset=True, by_alias=True))
        raw_json = self._call_api('/custom', params={}, body_json=request_json, call_type=CallType.POST)
        result = ScenarioDefinition.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    def delete_custom_scenario(self, scenario_id: UUID) -> Response[ScenarioDefinition]:
        """
        Performs a soft delete of the given custom scenario UUID in the database.

        :param scenario_id: unique ID of the scenario to delete
        :return: the soft-deleted scenario definition
        """
        raw_json = self._call_api(f'/custom/{str(scenario_id)}', {}, call_type=CallType.DELETE)
        result = ScenarioDefinition.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    def get_custom_scenario_versions(self, scenario_id: UUID) -> Response[List[ScenarioDefinition]]:
        """
        Lists all versions of the given custom scenario; note unlike getCustomSecenarios, the list of
        ScenarioDefinitions returned will all have the same UUID, just different version numbers. If
        the scenario was soft-deleted, the last version will have the deleted flag set.

        :return: all scenario versions for the given UUID
        """
        raw_json = self._call_api(f'/custom/{str(scenario_id)}/versions', {})
        results = [ScenarioDefinition.parse_obj(result) for result in raw_json['result']]
        return ScenariosApi._create_response_object(raw_json, results)

    def get_custom_scenarios(self, include_deleted: Optional[bool] = False) -> Response[List[ScenarioDefinition]]:
        """
        Lists all known custom scenarios, including the UUID's required for other operations. At this time
        it should be scoped to current organization, i.e. all entitled users for a given client site should
        be able to see all custom scenarios.

        :param include_deleted: whether to include soft-deleted custom scenarios for this installation
        :return: all known custom scenarios, or empty if none defined.
        """
        params = {'include_deleted': include_deleted}
        raw_json = self._call_api('/custom', params)
        results = [ScenarioDefinition.parse_obj(result) for result in raw_json['result']]
        return ScenariosApi._create_response_object(raw_json, results)

    def get_predefined_scenarios(self) -> Response[List[ScenarioDefinition]]:
        """
        Lists all versions of the given custom scenario; note unlike getCustomSecenarios, the list of
        ScenarioDefinitions returned will all have the same UUID, just different version numbers. If
        the scenario was soft-deleted, the last version will have the deleted flag set.

        :return: all known predefined scenarios
        """
        raw_json = self._call_api('/predefined', {})
        results = [ScenarioDefinition.parse_obj(result) for result in raw_json['result']]
        return ScenariosApi._create_response_object(raw_json, results)

    def get_scenario(self, scenario_id: UUID) -> Response[ScenarioDefinition]:
        """
        Helper method that gets a single scenario given a UUID. Normally the front-end will not use this:
        the expectation is that the relatively small universe of scenarios known to a particular
        organization will all be loaded via the getXxx operations.

        :return: the latest scenario version for the given scenario ID
        """
        raw_json = self._call_api(f'/{str(scenario_id)}', {})
        result = ScenarioDefinition.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    def get_scenario_result(self, run_id: UUID) -> Response[ScenarioResult]:
        """
        Given the UUID for a scenario run, gets its state and (if completed successfully) results.

        :param run_id: unique ID for the run result to retrieve
        """
        raw_json = self._call_api(f'/runs/{str(run_id)}/result', {})
        result = ScenarioResult.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    def get_scenario_run(self, run_id: UUID) -> Response[ScenarioRun]:
        """
        Gets a single run by its unique ID.

        :param run_id: unique ID of the run
        :return: the requested run
        """
        raw_json = self._call_api(f'/runs/{str(run_id)}', {})
        result = ScenarioRun.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    def get_scenario_runs(self, owner_id: str) -> Response[List[ScenarioRun]]:
        """
        Gets all scenario runs initiated by the current user.

        :param owner_id: username of the person who created this scenario run; if empty, return current
                         user's runs only (the normal case for Serenity UX)
        :return: all the user's runs, or empty if no runs
        """
        params = {'owner_id': owner_id}
        raw_json = self._call_api('/runs', params)
        result = ScenarioRun.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    def rollback_custom_scenario(self, scenario_id: UUID, version: int) -> Response[ScenarioDefinition]:
        """
        One-shot undo: roll back to previous version or if soft-deleted, restore a deleted scenario.

        :param scenario_id: the specific scenario to rollback
        :param version: version number to roll back to; this becomes the new, latest version
        :return: reverted definition; if it was deleted, soft delete flag will no longer be set on the result
        """
        params = {'version': version}
        raw_json = self._call_api(f'/rollback/{str(scenario_id)}', params, call_type=CallType.PATCH)
        result = ScenarioDefinition.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    def run_scenario(self, request: ScenarioRequest) -> Response[ScenarioResult]:
        """
        Given the UUID for a custom or predefined scenario, a portfolio and a set of runtime parameters,
        executes the scenario asynchronously. All known runs for the user can be listed and for now
        getScenarioRun can be polled to get the state and results. User ID should be specified in header.

        Note the client may either run a scenario by reference (UUID) or by value (ScenarioDefinition).
        The latter is used to allow the client to run arbitrary, transient scenarios.
        """
        request_json = json.loads(request.json(exclude_unset=True, by_alias=True))
        raw_json = self._call_api('/run', params={}, body_json=request_json, call_type=CallType.POST)
        result = ScenarioResult.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    def update_custom_scenario(self, scenario: ScenarioDefinition) -> Response[ScenarioDefinition]:
        """
        Stores a new version of the given custom scenario in the database.

        :param scenario: the initial definition to create, with version number equal to the
                        latest version number known to the client; the UUID is implied in
                        path and can be left out
        :return: updated definition with new version number, updated lastUpdated and lastUpdatedBy fields
        """
        request_json = json.loads(scenario.json(exclude_unset=True, by_alias=True))
        raw_json = self._call_api(f'/custom/{str(scenario.scenario_id)}', params={},
                                  body_json=request_json, call_type=CallType.PUT)
        result = ScenarioDefinition.parse_obj(raw_json['result'])
        return ScenariosApi._create_response_object(raw_json, result)

    @staticmethod
    def _create_response_object(raw_json: object, result: T) -> Response[T]:
        request_id = UUID(raw_json.get('requestId'))
        as_of_date = datetime.strptime(raw_json['asOfDate'], STD_DATE_FMT)
        warnings = raw_json.get('warnings', [])
        response = Response(request_id=request_id,
                            as_of_date=as_of_date,
                            warnings=warnings,
                            result=result)
        return response
