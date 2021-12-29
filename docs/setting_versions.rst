Setting Versions
===================

Over time, attributes of settings may change. These changes might be metadata differences, setting type changes, or
even wholesale renaming of the setting. These changes must as backwards compatible as possible, so that users using a
setting's older attributes might still function. At the same time, we want to make sure that these older declarations
don't regress the settings back to their old attributes. We consolidate those two needs with setting versions.

Whenever a setting is declared, it is declared with a version (the default version is ``1.0``). If the setting does not
yet exist, it is created (in this case, we expect the version to be ``1.0``). If the setting already exists, we check
the latest declared version of the setting. If the latest declared version is higher than the declaration version,
we inform the user that they are declaring with outdated attributes, but otherwise accept the declaration (without
modifying the setting data). If the latest declared version is lower than the declaration version, we update the setting
attributes to reflect the new declaration.

.. warning::

    Differing attributes are not checked for older versions. If a user purposely declares a setting with an older
    version but with different attributes then those used for that version, no error will be raised (but this will not
    affect other users whatsoever).

Note that not all changes are automatically accepted. If the new version is higher than the current version only in the
second number (what we call a **minor change**), only the following changes are accepted:

* Changing metadata.
* Changing the setting type to a :ref:`subtype <setting_types:Type Order>` of the current setting type.
* Renaming the setting (while defining the old name as an alias).
* Removing a configurable feature.
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
