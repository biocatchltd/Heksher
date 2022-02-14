API
============

Here we detail all the HTTP API endpoints, their payloads and the expected responses.
All endpoints return a JSON object, and those that expect a body in the request, expect it as a
JSON object.

Unless otherwise noted, all responses have the status code 200.

Since Heksher is a FastAPI service, the API can also be accessed via the redoc endpoint ``/redoc``.

The most common endpoints for users are :ref:`setting declaration <api:POST /api/v1/settings/declare>`,
and :ref:`querying <api:GET /api/v1/query>`

.. note::

    You can view the api in a swagger or redoc-style format locally by running heksher in :ref:`running:Doc Only Mode`

    .. code-block:: console

        docker run -d -p 9999:80 --name heksher-doc-only -e DOC_ONLY=true biocatchltd/heksher

    and accessing http://localhost:9999/redoc or http://localhost:9999/docs

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

GET /api/v1/query
**************************

.. note::

    This should be the primary endpoint that users call to get rule and setting default values.

.. note::

    This endpoint supports the
    `If-None-Match <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/If-None-Match>`_ header. It also returns
    an `ETag <https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/ETag>`_ header on successful responses.

Query the rules in the service, filtering in only rules pertaining to specific settings and contexts.

Query parameters:

* **settings**: A comma-seperated list of the names of the settings to query. If specified only rules that apply to one
  of the settings in this list will be returned. Example: ``../api/v1/query?settings=foo,bar``
* **context_filters**: A comma-seperated list of filters to filter rules by their context. If any filters are specified
  only rules all of whose exact-match context conditions match the relevant filters will be returned. Each filter is
  is a colon-separated pair. The first element of the pair is the context feature name, the second element is either
  the special character ``*`` to accept all values of the context feature, or a comma-seperated list of the values
  in parentheses. Example: ``../api/v1/query?context_filters=foo:*,bar:(a,b)``. Alternatively, the context_filters
  can be the special character ``*`` to accept all context features (this is the default behaviour).

  .. note:: Context Filter Example

      Assuming a setting has the context features ``X``, ``Y``, and ``Z``, and the following rules:

      .. csv-table::
        :header: "X", "Y", "Z", "**rule_id**"

        "x_0", "\*", "\*", "1"
        "x_1", "\*", "\*", "2"
        "x_0", "y_0", "\*", "3"
        "x_0", "y_1", "\*", "4"
        "x_2", "y_0", "\*", "5"
        "\*", "\*", "z_0", "6"
        "x_0", "\*", "z_0", "7"

      The the context filter: ``X:(x_0,x_1),Y:*`` will only allow the rules ``1``, ``2``, ``3``, and ``4``. Rule ``5`` will
      be rejected because it's X condition is not in the X filter's list of values. Rules ``6`` and ``7`` will be rejected
      because they have a Z condition and there is no Z filter.

* **include_metadata** (default false): If true, then the metadata associated with each rule will be included in
  the results.

Response:

* **settings**: A dictionary that maps setting names to query results of that setting and pass the filters in the
  request. Each value is a dictionary with the following keys:

    * **rules**: A list of rule dictionaries, that contains all teh rules that met the query criteria. Each rule
      dictionary has the following keys:

        * **value**: The value a setting should take if the rule is matched.
        * **feature_values**: An array of 2-str-arrays of the context feature names and values that the rule applies to, in order
          of the context features.
        * **metadata**: A dictionary of metadata associated with the rule. Only present if include_metadata is true.

    * **default_value**: The default value of the setting.

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

GET /api/v1/rules/search
***************************

Find a rule by its setting and feature_values.

Query parameters:

* **setting**: The name of the setting the rule to applies to.
* **feature_values**: A comma-seperated list of colon-seperated pairs context features and their values that the rule
  should apply to. Example: ``../api/v1/rules/search?setting=foo&feature_values=bar:a,baz:b``

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
of existing settings (while retaining compatibility, see :ref:`setting_versions:Setting Versions`).

Request:

* **name**: The name of the setting.
* **configurable_features**: A list of context feature names that the setting will be configurable with.
* **type**: The type of the setting. (see :ref:`setting_types:Setting Types`)
* **default_value** (optional): The default value of the setting.
* **metadata** (optional): A dictionary of metadata associated with the setting.
* **alias** (optional): An alias of the setting. Must either be an existing alias of the setting, or a canonical name of
  an existing setting.
* **version** (optional): The version of the setting declaration, defaults to "1.0".


Response:

* **outcome**: one of the following values:
    * ``"created"``: The setting was newly created.
    * ``"uptodate"``: The setting declaration matches the latest declaration.
    * ``"upgraded"``: The setting's attributes were changed to reflect this new declaration.
    * ``"outdated"``: This declaration is superseded by a newer declaration. It is up to the user whether to proceed.
    * ``"rejected"``: The setting's attributes were not changed due to an incompatible difference with the newer
      version. In this case, the response code will be 409.
    * ``"mismatch"``: the setting's declaration is not compatible with the current version of the service. In this
      case, the response code will be 409.
* **latest_version**: The latest version of the setting declaration. Only present for ``"outdated"`` outcomes.
* **previous_version**: The previous version of the setting declaration. Only present for ``"upgraded"`` and
  ``"rejected"`` outcomes.
* **differences**: A list of differences between the request declaration and the latest declaration. Only present for
  ``"outdated"``, ``"upgraded"``, ``"rejected"``, and ``"mismatch"`` outcomes. Each difference is a dictionary with the
  following possible keys:

    * **level**: one of the following values:

        * ``"minor"``: The difference is fully backwards compatible with previous declarations (of the same major version).
        * ``"major"``: The difference is incompatible with previous declarations.
        * ``"mismatch"``: The difference cannot be implemented because it would break internal logic.

    * **attribute**: The name of the attribute that is different. Either this key or the "message" key exists.
    * **latest_value**: The value of the attribute in the latest declaration. Either this key or the "message" key
      exists.
    * **message**: A human-readable description of the difference.

    .. note::
        If the outcome is "outdated", then all the differences will be in the sense of the differences that occurred
        since that declaration. Meaning that if the declaration request has one more configurable feature than the
        latest declaration, then the change will have a level of "minor".


If there is a difference between the setting's declared and actual values that cannot be consolidated, a 409 response
will be returned.

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
* **version**: The version of the latest setting declaration.

GET /api/v1/settings
**********************

Get all defined settings.

Query Parameters:

* **include_additional_data** (optional): If true, the response will include all data about all settings. If false (the
  default), the response will only include the name of each setting.

Response:

* **settings**: A list of dictionaries describing each setting. Each element of the list is of the schema:

    * **name**: The name of the setting.
    * **type**: The type of the setting.
    * **default_value**: The default value of the setting.
    * **version**: The version of the latest setting declaration.
    * **configurable_features**: A list of context feature names that the setting will be configurable with. Only included
      if include_additional_data is true.
    * **metadata**: A dictionary of metadata associated with the setting. Only included if include_additional_data is true.
    * **aliases**: A list aliases of the setting. Only included if include_additional_data is true.

PUT /api/v1/settings/<setting_name>/type
*******************************************

Change a setting's type in a way that is not necessarily backwards compatible.

Request:

* **type**: The new type of the setting.
* **version**: The version of the setting declaration.

The type will only be changed if the default value of the setting and the values of a all the rules of the setting are
compatible with the new type. If this the case, an empty 204 response will be returned.

If there are type conflicts, the 409 response will have the schema:

* **conflicts**: A list of strings describing the conflicts.

PUT /api/v1/settings/<setting_name>/name
*********************************************

Rename a setting.

Request:

* **name**: The new name of the setting.
* **version**: The version of the setting declaration.

The name will only be changed if the name is not already in use. If this the case, the old name will be added as an 
alias to the setting and an empty 204 response will be returned.

If the new name is already in use, or if the version is incompatible with the latest declaration, a 409 response will
be returned.

PUT /api/v1/settings/<setting_name>/configurable_features
***********************************************************

Change the configurable features of a setting.

Request:

* **configurable_features**: A list of context feature names that the setting will be configurable with.
* **version**: The version of the setting declaration.

Response is an empty 204 response.

POST /api/v1/settings/<setting_name>/metadata
************************************************

Update a setting's metadata. This will not delete existing keys, but might overwrite existing keys with new values.

Request:

* **metadata**: A dictionary of metadata to associate with the setting.
* **version**: The version of the setting declaration.

Response is an empty 204 response.

PUT /api/v1/settings/<setting_name>/metadata
***********************************************

Set a setting's metadata. This will overwrite any existing metadata.

Request:

* **metadata**: A dictionary of metadata to associate with the setting.
* **version**: The version of the setting declaration.

Response is an empty 204 response.

DELETE /api/v1/settings/<setting_name>/metadata
*****************************************************

Remove all metadata associated with a setting. This is equivalent to calling
`PUT /api/v1/settings/<setting_name>/metadata`_ with an empty dictionary.

Request:

* **version**: The version of the setting declaration.

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
* **version**: The version of the setting declaration.

Response is an empty 204 response.

DELETE /api/v1/settings/<setting_name>/metadata/<key>
*******************************************************

Remove a key from a setting's metadata.

Request:

* **version**: The version of the setting declaration.

Response is an empty 204 response.