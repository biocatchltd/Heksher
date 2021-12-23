API
============

Here we detail all the HTTP API endpoints, their payloads and the expected responses.
All endpoints return a JSON object, and those that expect a body in the request, expect it as a
JSON object.

Unless otherwise noted, all responses have the status code 200.

Since Heksher is a FastAPI service, the API can also be accessed via the redoc endpoint ``/redoc``.

The most common endpoints for users are :ref:`setting declaration <api:POST /api/v1/settings/declare>`,
and :ref:`rule querying <api:POST /api/v1/rules/query>`

General
-------

GET /redoc
*************

Returns an HTML page with the redoc documentation for the API.

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

* **context_features**: A list of the context feature names, in order.

GET /api/v1/context_features/<feature>
**************************************

Check whether a context feature exists, and get its index.

if the context feature does not exist, returns a 404 response.

Otherwise the response schema is:

* **index**: The index of the context feature.

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
    * **to_after**: the name of the context feature that should be before the one being moved.
* Or specify the context feature that should be after it:
    * **to_before**: the name of the context feature that should be after the one being moved.

The context features are reordered so that the current context feature is now in the appropriate position as
specified by the request. Returns a 204 response.

POST /api/v1/context_features
*******************************

Add a new context feature.

Request:

* **context_feature**: The name of the context feature to add.

If a context feature with the same name already exists, returns a 409.

Otherwise, returns a 204 response.

Rules
-----

POST /api/v1/rules
********************

Create a new rule.

Request:

* **setting**: The name of the setting for the rule to apply to.
* **feature_values**: A dictionary of the values of the context features that the rule should apply to.
* **value**: The value a setting should take if the rule is matched.
* **metadata**: A dictionary of metadata to associate with the rule.

If a rule with the same setting and feature_values already exists, returns a 409.

otherwise, returns a 201 response, with the following schema:

* **rule_id**: The id of the rule that was created.

DELETE /api/v1/rules/<rule_id>
*******************************

Delete a rule.

Responds with a 204 response.

POST /api/v1/rules/search
***************************

Find a rule by its setting and feature_values.

Request:

* **setting**: The name of the setting the rule to applies to.
* **feature_values**: A dictionary of the values of the context features that the rule should apply to.

If a rule does not exists to that setting and feature_values, returns a 404 response.

Otherwise, the response schema is:

* **rule_id**: The id of the rule that was found.

PUT /api/v1/rules/<rule_id>/value
**********************************

Change a rule's value.

Request:

* **value**: The new value for the rule.

Responds with a 204 response.

PATCH /api/v1/rules/<rule_id>
**********************************

A deprecated route that is equivalent to `PUT /api/v1/rules/<rule_id>/value`_.

POST /api/v1/rules/query
**************************

.. note::

    This should be the primary endpoint that users call to get rules.

Query the rules in the service, filtering in only rules pertaining to specific settings and contexts.

Request:

* **setting_names**: A list of the names of the settings to query. Only rules that apply to one of the
  settings in this list will be returned.
* **context_feature_options**: A dictionary that maps context feature names to arrays of values to consider when
  querying. Only rules whose exact-match conditions are all in the respective arrays will be returned. Alternatively,
  a context feature value list can be replaced with the string "*" to indicate that all values of that context feature
  should be considered. Finally, the entire dictionary can be replaced with the string "*" to indicate that all rules
  should be returned, regardless of their condition.
* **cache_time** (optional): The timestamp of the user's cache for this query. If provided, then only settings that have
  been changed since this timestamp will be returned (the rest will be omitted from the results).
* **include_metadata** (optional, default false): If true, then the metadata associated with each rule will be included in
  the results.

Response:

* **rules**: A dictionary that maps setting names to arrays of rules that apply to that setting and pass the filters in the
  request. If a setting has not been changed since the cache_time, then it will not be in the result.
  Each rule is a dictionary with the following keys:

    * **value**: The value a setting should take if the rule is matched.
    * **feature_values**: An array of 2-str-arrays of the context feature names and values that the rule applies to, in order
      of the context features.
    * **metadata**: A dictionary of metadata associated with the rule. Only present if include_metadata is true.

GET /api/v1/rules/<rule_id>
***************************

Get a rule's data by its id.

Response:

* **setting**: The name of the setting the rule applies to.
* **value**: The value a setting should take if the rule is matched.
* **feature_values**: An array of 2-str-arrays of the context feature names and values that the rule applies to, in order
  of the context features
* **metadata**: A dictionary of metadata associated with the rule.

POST /api/v1/rules/<rule_id>/metadata
*****************************************

Update a rule's metadata. This will not delete existing keys, but might overwrite existing keys with new values.

Request:

* **metadata**: A dictionary of metadata to associate with the rule.

Response is an empty 204 response.

PUT /api/v1/rules/<rule_id>/metadata
**************************************

Set a rule's metadata. This will overwrite any existing metadata.

Request:

* **metadata**: A dictionary of metadata to associate with the rule.

Response is an empty 204 response.

DELETE /api/v1/rules/<rule_id>/metadata
****************************************

Remove all metadata associated with a rule. This is equivalent to calling `PUT /api/v1/rules/<rule_id>/metadata`_ with
an empty dictionary.

Response is an empty 204 response.


GET /api/v1/rules/<rule_id>/metadata
*********************************************

Get a rule's metadata.

Response:

* **metadata**: A dictionary of metadata associated with the rule.

PUT /api/v1/rules/<rule_id>/metadata/<key>
*******************************************

Set the value of a key in a rule's metadata.

Request:

* **value**: The value to associate with the key.

Response is an empty 204 response.

DELETE /api/v1/rules/<rule_id>/metadata/<key>
*********************************************

Remove a key from a rule's metadata.

Response is an empty 204 response.

Settings
----------

POST /api/v1/settings/declare
*******************************

.. note::

    This is the primary endpoint that users call to create and assert the state of settings.

Declare that a setting will be used by a service. This endpoint can be used to create new settings or change attributes
of existing settings (while retaining compatibility).

Request:

* **name**: The name of the setting.
* **configurable_features**: A list of context feature names that the setting will be configurable with.
* **type**: The type of the setting. (see :ref:`setting_types:Setting Types`)
* **default_value** (optional): The default value of the setting.
* **metadata** (optional): A dictionary of metadata associated with the setting.
* **alias** (optional): An alias of the setting.

Response:

* **created**: True if the setting was created, false if it already existed.
* **changed**: An array of strings that describe the attributes of the setting that changed due to the declaration.
* **incomplete**: An dictionary describes the attributes of the setting were declared in an incomplete manner. The
  dictionary maps attribute names to their complete values.

If there is a difference between the setting's declared and actual values that cannot be consolidated, a 409 response
will be returned.

Heksher will attempt to consolidate the following differences, if they exist:

* If the declaration contains configurable_features that do not exist in the setting, they will be added to the setting.

    * If the declaration does not contains configurable_features that do exist in the setting, they will **not** be removed
      from the setting, the complete value will be indicated in the response.

* If the type declared is a supertype of the actual type, the actual type will be updated to the declared type.

    * If the type declared is a subtype of the actual type, the complete value will be indicated in the response.

* If the default value declared is different from the actual default value, the actual default value will be updated to
  the declared default value.
* If the metadata declared is different from the actual metadata, the actual metadata will be changed to the declared
  metadata.
* If the alias refers to an existing setting, and the name is not an existing setting. Then the old setting (under
  alias) will be renamed to the new name, and the old name will be added as an alias to it.

DELETE /api/v1/settings/<name>
******************************

Remove a setting. This will permanently remove the setting from the system.

Response is an empty 204 response.

GET /api/v1/settings/<name>
*****************************

Get data about a setting.

Response:

* **name**: The name of the setting.
* **configurable_features**: A list of context feature names that the setting will be configurable with.
* **type**: The type of the setting.
* **default_value**: The default value of the setting.
* **metadata**: A dictionary of metadata associated with the setting.
* **aliases**: A list aliases of the setting.

GET /api/v1/settings
**********************

Get all defined settings.

Query Parameters:

* **include_additional_data** (optional): If true, the response will include all data about all settings. If false (the
  default), the response will only include the name of each setting.

Response:

* **settings**: A list of dictionaries describing each setting. Each element of the list is of the schema:

    * **name**: The name of the setting.
    * **configurable_features**: A list of context feature names that the setting will be configurable with. Only included
      if include_additional_data is true.
    * **type**: The type of the setting. Only included if include_additional_data is true.
    * **default_value**: The default value of the setting. Only included if include_additional_data is true.
    * **metadata**: A dictionary of metadata associated with the setting. Only included if include_additional_data is true.
    * **aliases**: A list aliases of the setting. Only included if include_additional_data is true.

PUT /api/v1/settings/<name>/type
********************************

Change a setting's type in a way that is not necessarily backwards compatible.

Request:

* **type**: The new type of the setting.

The type will only be changed if the default value of the setting and the values of a all the rules of the setting are
compatible with the new type. If this the case, an empty 204 response will be returned.

Other wise, the 409 response will have the schema:

* **conflicts**: A list of strings describing the conflicts.

PUT /api/v1/settings/<name>/name
*********************************

Rename a setting.

Request:

* **name**: The new name of the setting.

The name will only be changed if the name is not already in use. If this the case, the old name will be added as an 
alias to the setting and an empty 204 response will be returned.

If the new name is already in use, the 409 response will be returned.

POST /api/v1/settings/<setting_name>/metadata
************************************************

Update a setting's metadata. This will not delete existing keys, but might overwrite existing keys with new values.

Request:

* **metadata**: A dictionary of metadata to associate with the setting.

Response is an empty 204 response.

PUT /api/v1/settings/<setting_name>/metadata
***********************************************

Set a setting's metadata. This will overwrite any existing metadata.

Request:

* **metadata**: A dictionary of metadata to associate with the setting.

Response is an empty 204 response.

DELETE /api/v1/settings/<setting_name>/metadata
*****************************************************

Remove all metadata associated with a setting. This is equivalent to calling
`PUT /api/v1/settings/<setting_name>/metadata`_ with an empty dictionary.

Response is an empty 204 response.


GET /api/v1/settings/<setting_name>/metadata
*********************************************

Get a setting's metadata.

Response:

* **metadata**: A dictionary of metadata associated with the setting.

PUT /api/v1/settings/<setting_name>/metadata/<key>
*****************************************************

Set the value of a key in a setting's metadata.

Request:

* **value**: The value to associate with the key.

Response is an empty 204 response.

DELETE /api/v1/settings/<setting_name>/metadata/<key>
*******************************************************

Remove a key from a setting's metadata.

Response is an empty 204 response.