Libraries
==========

Heksher currently has only one official support library, which is
`heksher SDK for python <https://heksher-py.readthedocs.io/en/latest/>`_, supporting both synchronous and async
continuous updates.

.. code-block::

    cache_ttl = heksher.Setting(name="cache_ttl", type=int,
                                configurable_feature=['environment', 'user'], default_value=60)
    ...

    heksher_client = heksher.AsyncHeksherClient(
                service_url = ...,
                update_interval = 300,  # update all settings every 5 minutes
                context_features = ['environment', 'user', 'theme'],
                http_client_args = {'headers': {'api_token': ...}},
            )
    await heksher_client.set_as_main()
    ...
    cache_ttl.get(user='guest')