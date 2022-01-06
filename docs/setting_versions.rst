Setting Versions
===================

Over time, attributes of settings may change. These changes might be metadata differences, setting type changes, or
even wholesale renaming of the setting. These changes must be as backwards compatible as possible, so that users using a
setting's older attributes might still function. At the same time, we want to make sure that these older declarations
don't regress the settings back to their old attributes. We consolidate those two needs with setting versions.

Whenever a setting is declared, it is declared with a version (the default version is ``1.0``).If the setting does not
yet exist, it is created (in this case, we expect the version to be ``1.0``). If the setting already exists, we check
the latest declared version of the setting.

* If the latest declared version is the same as the current version, we assert that the values are the same as the
  latest declaration. If the assertion fails, we inform the user of an attribute mismatch.
* If the latest declared version is higher than the declaration version, we inform the user that they are declaring with
  outdated attributes.
    .. warning::

        Differing attributes are not checked for older versions. If a user purposely declares a setting with an older
        version but with different attributes then those used for that version, no issue will be reported (but this will not
        affect other users whatsoever). This behavior might change in the future.

* If the latest declared version is lower than the declaration version, we update the setting attributes to reflect the
  new declaration.


Note that not all changes are automatically accepted. If the new version is higher than the current version only in the
second number (what we call a **minor change**), only the following changes are accepted:

* Changing metadata.
* Changing the setting type to a :ref:`subtype <setting_types:Type Order>` of the current setting type.
* Renaming the setting (while defining the old name as an alias).
* Removing a configurable feature that no rule of the setting is configured by.
* Changing a default value.

.. note::

    These are changes that we expect to be fully backwards compatible. i.e. if a setting is declared with an older
    version, we expect to be fully functional.

If the new version is higher than the current version in the first number (what we call a **major change**), we accept
the following changes:

 * Changing metadata.
 * Changing the setting type.
 * Renaming the setting (while defining the old name as an alias).
 * Changing configurable features.
 * Changing a default value.

There are some changes that are never acceptable, as they would break the logic of the application. These are:

* Changing a setting type to a value that does not accept the value of at least one rule of the setting.
* Removing configurable features that are matched by at least one rule of the setting.

Explicit Versioning
--------------------

For most use cases, upgrading a setting via the declaration API is sufficient. However, there are some changes that
might fail depending on the state of the ruleset of the service. If these conflicts are encountered with the declaration
API, our app might fail. To avoid this, these potentially conflicting changes can be made explicit with explicit API
calls. These API endpoints are:

* :ref:`PUT /api/v1/settings/setting_name>/configurable_features`
* :ref:`PUT /api/v1/settings/setting_name>/type`