Abstract Concepts
====================

Heksher has 3 basic entities that interact with each other:

Setting
------------------
A setting is a variable whose value depends on the context. Each setting is identified by its name and has the following
attributes:

* name: The name of the setting. This also serves as its unique identifier.
* configurable_features: Which `context features`_ the setting is configurable for.
* type: the :ref:`types <setting_types:Setting Types>` of the setting.
* metadata: additional metadata about the setting.
* aliases: a list of :ref:`aliases <setting_aliases:Setting Aliases>` of the setting.
* default: the default value of the setting. Optional.

Context Features
-----------------------
A context feature is a variable that indicates the context a setting can be configured by. For example, if a setting's
value is dependant on the tenant, then the tenant is a context feature of the service.

Each heksher service has an ordered list of context features. The order of the context features is important. The
firstmost features are more general and have a lower priority, while the lastmost features are more specific and have
a higher priority.

.. _context:

A "context" is essentially a value given to context features. For example, if an heksher service has the context
features ``["environmnt", "tenant", "subtenant"]``, then an example context might be
``{"environment": "dev", "tenant": "john", "subtenant": "default"}``.

Rules
------------------
A rule is a set of conditions that, when met by a `context`_, set a value for a specific `setting`_. Following up from
the previous example, an example rule might be: `if an environment is "dev" and a tenant is "john", then set the setting
"background_color" to "navy blue"`. Note that the this rule will be met for any context that has both the "dev"
environment and the "john" tenant, regardless of any other context feature value. Indeed, a rule's condition is an
intersect of exact-match predicates over the specific context features.

Rules do not exist on their own, many setting will have multiple rules over them. For an example we will have the
setting "theme" (configurable only via the "environment" and "tenant" context features) with the following rules:

#. if the environment is "dev", then set the setting to "light"
#. if the environment is "prod", then set the setting to "dark"
#. if the environment is "dev" and the tenant is "john", then set the setting to "dark"
#. if the tenant is "jane", then set the setting to "halloween"
#. if the tenant is "admin", then set the setting to "matrix"
#. if the tenant is "guest", then set the setting to "default"

Rule Priority
^^^^^^^^^^^^^^^^^^^^^^^
When observing the above list, a question might be raised: what happens if we our context is valid for multiple rules?
for example, if we have the context ``{"environment": "dev", "tenant": "admin"}``, then we will match both rules 1 and
5, so what will be the setting's value? This is where the order of the context features comes into play. In general,
when multiple rules are met, the rule with latest exact-match context feature condition will be used (with the
next-latest condition as a tie-breaker). So in the example provided, rule number 5 will be used, since the "tenant"
context feature is later than "environment" in the order of context features.

It might be useful to conceptually order the rules in a table, like so:


.. csv-table::
    :header: "environment", "tenant", "**value**"

    dev, john, **dark**
    , admin, **matrix**
    , john, **halloween**
    , guest, **default**
    dev, , **light**
    prod, , **dark**

Now the rules are ordered by their priority, with the uppermost rule having the highest priority.
