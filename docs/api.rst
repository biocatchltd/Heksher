API
============

Here we detail all the HTTP API endpoints, their payloads and the expected responses.
All endpoints return a JSON object, and those that expect a body in the request, expect it as a
JSON object.

Unless otherwise noted, all responses have the status code 200.

General
-------

GET /api/health
***********************

endpoint to check if the server is up and running, and whether the connection to the postgresql
database is good.

The response code will be 200 if the database is reachable or 500 if it is not.

responds with a JSON object with only one field: ``"version"``, which is the version of the
Heksher server.

.. note::

    Rather than checking the database connection on every call, heksher performs an automatic health
    check every 5 seconds. Therefore, all health responses may be up to 5 seconds out of date.

Context Features
-----------------

GET /api/v1/context_features
********************************

Get all the context features currently defined for the service, in order.

Response:

* context_features: A list of the context feature names, in order.

GET /api/v1/context_features/<feature>
**************************************

Check whether a context feature exists, and get its index.

if the context feature does not exist, returns a 404 response.

Otherwise the response schema is:

* index: The index of the context feature.

DELETE /api/v1/context_features/<feature>
******************************************

Delete a context feature. This endpoint will fail if the context feature is in use (i.e. if there
are any settings that are configurable by it).

If the context feature is in use, returns a 409 response.
Otherwise, returns a 204 response.

PATCH /api/v1/context_features/<feature>/index
************************************************

Change the index of a context feature.

Expects a body that is one of the following:

* Either specify the context feature that should be before it:
    * to_after: the name of the context feature that should be before the one being moved.
* Or specify the context feature that should be after it:
    * to_before: the name of the context feature that should be after the one being moved.

Otherwise, the context features are reordered so that the current context feature is now in the appropriate position as
specified by the request. Returns a 204 response.

POST /api/v1/context_features
*******************************

Add a new context feature.

Request:

* context_feature: The name of the context feature to add.

If a context feature with the same name already exists, returns a 409.
Otherwise, returns a 204 response.

Rules
-----

POST /api/v1/rules
********************

Create a new rule.

Request:

* setting: The name of the setting for the rule to apply to.
* feature_values: A dictionary of the values of the context features that the rule should apply to.
* value: The value a setting should take if the rule is matched.
* metadata: A dictionary of metadata to associate with the rule.

If a rule with the same setting and feature_values already exists, returns a 409.

otherwise, returns a 201 response, with the following schema:

* rule_id: The id of the rule that was created.

DELETE /api/v1/rules/<rule_id>
*******************************

Delete a rule.

Responds with a 204 response.

POST /api/v1/rules/search
***************************

Find a rule by its setting and feature_values.

Request:

* setting: The name of the setting the rule to applies to.
* feature_values: A dictionary of the values of the context features that the rule should apply to.

If a rule does not exists to that setting and feature_values, returns a 404 response.

Otherwise, the response schema is:

* rule_id: The id of the rule that was found.

PATCH /api/v1/rules/<rule_id>
******************************

Change a rule's value.

Request:

* value: The new value for the rule.

Responds with a 204 response.

POST /api/v1/rules/query
**************************

.. note::

    This should be the primary endpoint that users call to get rules.

Query the rules in the service, filtering in only rules pertaining to specific settings and contexts.

Request:

* setting_names: A list of the names of the settings to query. Only rules that apply to one of the
  settings in this list will be returned.
* context_feature_options: A dictionary that maps context feature names to arrays of values to consider when
  querying. Only rules whose exact-match conditions are all in the respective arrays will be returned. Alternatively,
  a context feature value list can be replaced with the string "*" to indicate that all values of that context feature
  should be considered. Finally, the entire dictionary can be replaced with the string "*" to indicate that all rules
  should be returned, regardless of their condition.
* cache_time (optional): The timestamp of the user's cache for this query. If provided, then only settings that have
  been changed since this timestamp will be returned (the rest will be omitted from the results).
* include_metadata (optional, default false): If true, then the metadata associated with each rule will be included in
  the results.

Response:

* rules: A dictionary that maps setting names to arrays of rules that apply to that setting and pass the filters in the
  request. If a setting has not been changed since the cache_time, then it will not be in the result.
  Each rule is a dictionary with the following keys:
    * value: The value a setting should take if the rule is matched.
    * feature_values: An array of 2-str-arrays of the context feature names and values that the rule applies to, in order
      of the context features.
    * metadata: A dictionary of metadata associated with the rule. Only present if include_metadata is true.

GET /api/v1/rules/<rule_id>
***************************

Get a rule's data by its id.

Response:
* setting: The name of the setting the rule applies to.
* value: The value a setting should take if the rule is matched.
* feature_values: An array of 2-str-arrays of the context feature names and values that the rule applies to, in order
  of the context features
* metadata: A dictionary of metadata associated with the rule.